"""Public, unauthenticated API consumed by the mobile app. Read-only except device registration."""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import client_ip
from app.core.errors import not_found
from app.core.ratelimit import limiter
from app.core.text import utcnow
from app.db import get_db
from app.models import (
    Article,
    DevicePlatform,
    LegalDocument,
    OrganizationProfile,
    Performance,
    PermissionState,
    Production,
    PushDevice,
    Visibility,
)
from app.notifications.providers import is_valid_token
from app.schemas.common import PageNo, PageSize, StrictModel
from app.services import queries, serialize
from app.services.media import image_dict

router = APIRouter(prefix="/api/v1", tags=["public"])

REPERTOIRE_MAX = 12  # home screen strip; a horizontal carousel stops being useful well before this


def _page(items: list, page: int, page_size: int) -> dict:
    start = (page - 1) * page_size
    return {"items": items[start:start + page_size], "total": len(items), "page": page, "page_size": page_size}


@router.get("/home", summary="Home screen content")
def home(db: Session = Depends(get_db)):
    productions, summary = queries.search_productions(db)
    featured = [p for p in productions if p.is_featured]
    source = "featured"
    if not featured:
        featured, source = [p for p in productions if p.on_stage], "on_stage"
    if not featured:
        featured, source = [p for p in productions if p.id in summary], "upcoming"

    def card(p: Production) -> dict:
        cnt, nxt = summary.get(p.id, (0, None))
        return serialize.production_card(p, nxt, cnt)

    # The repertoire strip is curated: productions given a home position, left to right. Until an editor
    # has chosen any, it falls back to the most recently published ones so the section is never empty.
    repertoire = sorted(
        (p for p in productions if p.home_order is not None),
        key=lambda p: (p.home_order, queries.fold(p.title)),
    )[:REPERTOIRE_MAX]
    if not repertoire:
        repertoire = sorted(
            (p for p in productions if p.first_published_at),
            key=lambda p: (p.first_published_at, p.sort_order * -1),
            reverse=True,
        )[:6]
    upcoming = db.scalars(queries.public_performances(include_cancelled=False).limit(10)).unique().all()
    articles = db.scalars(
        select(Article)
        .where(Article.status == Visibility.published, Article.published_at <= utcnow())
        .order_by(Article.published_at.desc())
        .limit(3)
    ).unique().all()
    return {
        "featured": [card(p) for p in featured[:8]],
        "featured_source": source,
        "upcoming": [serialize.performance_public(x) for x in upcoming],
        # Named for its original content; the app shows it as the "Repertuvar" strip.
        "new_productions": [card(p) for p in repertoire],
        "articles": [serialize.article_public(a) for a in articles],
    }


@router.get("/productions", summary="Searchable, filterable catalogue of published productions")
def list_productions(
    q: Annotated[str | None, Query(max_length=100)] = None,
    genre: Annotated[str | None, Query(max_length=60)] = None,
    has_upcoming: bool | None = None,
    on_stage: bool | None = None,
    page: PageNo = 1,
    page_size: PageSize = 50,
    db: Session = Depends(get_db),
):
    productions, summary = queries.search_productions(db, q=q, genre=genre, has_upcoming=has_upcoming,
                                                      on_stage=on_stage)
    cards = [serialize.production_card(p, summary.get(p.id, (0, None))[1], summary.get(p.id, (0, None))[0])
             for p in productions]
    return _page(cards, page, page_size)


@router.get("/genres", summary="Genres used by published productions")
def list_genres(db: Session = Depends(get_db)):
    return {"items": queries.genres(db)}


@router.get("/productions/{slug}", summary="Production detail with upcoming performances")
def production_detail(slug: str, db: Session = Depends(get_db)):
    p = db.scalars(queries.public_productions().where(Production.slug == slug)).unique().first()
    if not p:
        raise not_found("Oyun bulunamadı.")
    perfs = db.scalars(queries.public_performances().where(Performance.production_id == p.id)).unique().all()
    return serialize.production_detail(p, list(perfs))


@router.get("/performances", summary="Upcoming public schedule (chronological)")
def schedule(
    production: Annotated[str | None, Query(max_length=160, description="production slug")] = None,
    include_cancelled: bool = True,
    page: PageNo = 1,
    page_size: PageSize = 50,
    db: Session = Depends(get_db),
):
    stmt = queries.public_performances(include_cancelled=include_cancelled)
    if production:
        stmt = stmt.where(Production.slug == production)
    perfs = db.scalars(stmt).unique().all()
    return _page([serialize.performance_public(x) for x in perfs], page, page_size)


@router.get("/articles", summary="Published announcements, newest first")
def list_articles(page: PageNo = 1, page_size: PageSize = 20, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Article)
        .where(Article.status == Visibility.published, Article.published_at <= utcnow())
        .order_by(Article.published_at.desc())
    ).unique().all()
    return _page([serialize.article_public(a) for a in rows], page, page_size)


@router.get("/articles/{slug}")
def article_detail(slug: str, db: Session = Depends(get_db)):
    a = db.scalars(
        select(Article).where(
            Article.slug == slug, Article.status == Visibility.published, Article.published_at <= utcnow()
        )
    ).unique().first()
    if not a:
        raise not_found("Duyuru bulunamadı.")
    return serialize.article_public(a, full=True)


@router.get("/organization", summary="Organisation profile and About content")
def organization(db: Session = Depends(get_db)):
    org = db.get(OrganizationProfile, 1)
    if not org:
        raise not_found("Kurum bilgisi henüz girilmemiş.")
    return {
        "name": org.name,
        "short_name": org.short_name,
        "address": org.address,
        "phones": org.phones or [],
        "email": org.email,
        "website_url": org.website_url,
        "instagram_url": org.instagram_url,
        "x_url": org.x_url,
        "youtube_url": org.youtube_url,
        "about": org.about or {},
        "logo": image_dict(org.logo),
    }


@router.get("/legal", summary="Published legal documents applicable to the mobile app")
def legal_list(db: Session = Depends(get_db)):
    docs = db.scalars(
        select(LegalDocument)
        .where(LegalDocument.status == Visibility.published, LegalDocument.applies_to.in_(["mobile_app", "all"]))
        .order_by(LegalDocument.title)
    ).all()
    return {"items": [{"slug": d.slug, "title": d.title,
                       "updated_at": (d.published_at or d.updated_at).isoformat()} for d in docs]}


@router.get("/legal/{slug}")
def legal_detail(slug: str, db: Session = Depends(get_db)):
    d = db.scalar(select(LegalDocument).where(LegalDocument.slug == slug, LegalDocument.status == Visibility.published))
    if not d:
        raise not_found("Belge bulunamadı.")
    return {"slug": d.slug, "title": d.title, "body": d.body, "applies_to": d.applies_to,
            "updated_at": (d.published_at or d.updated_at).isoformat()}


# ---------------------------------------------------------------- push device registration

_INSTALLATION_RE = re.compile(r"^[A-Za-z0-9-]{16,64}$")


class DeviceIn(StrictModel):
    installation_id: str = Field(description="Random per-install identifier generated by the app")
    platform: DevicePlatform
    permission: PermissionState
    push_token: str | None = Field(default=None, max_length=255)
    app_version: str | None = Field(default=None, max_length=40)
    locale: str | None = Field(default=None, max_length=20)

    @field_validator("installation_id")
    @classmethod
    def _iid(cls, v: str) -> str:
        if not _INSTALLATION_RE.match(v):
            raise ValueError("Geçersiz kurulum kimliği.")
        return v

    @field_validator("push_token")
    @classmethod
    def _token(cls, v: str | None) -> str | None:
        if v is not None and not is_valid_token(v):
            raise ValueError("Geçersiz bildirim anahtarı.")
        return v


class DeviceOut(StrictModel):
    active: bool


@router.post("/devices", response_model=DeviceOut, summary="Register or refresh this installation for push")
def register_device(body: DeviceIn, request: Request, db: Session = Depends(get_db)):
    limiter.hit(f"devices:{client_ip(request)}", limit=30, window_seconds=60)
    now = utcnow()
    device = db.scalar(select(PushDevice).where(PushDevice.installation_id == body.installation_id))
    if device is None:
        device = PushDevice(installation_id=body.installation_id, platform=body.platform)
        db.add(device)

    if body.push_token and body.push_token != device.push_token:
        # A token can only belong to one installation (e.g. after reinstall): detach it elsewhere.
        other = db.scalar(select(PushDevice).where(PushDevice.push_token == body.push_token))
        if other and other is not device:
            other.push_token = None
            other.is_active = False
            other.deactivated_at = now
            other.deactivation_reason = "token_moved"
            db.flush()
        device.push_token = body.push_token

    device.platform = body.platform
    device.permission = body.permission
    device.app_version = body.app_version
    device.locale = body.locale
    device.last_seen_at = now
    active = body.permission == PermissionState.granted and device.push_token is not None
    if active:
        device.is_active, device.deactivated_at, device.deactivation_reason = True, None, None
    else:
        if device.is_active or device.deactivated_at is None:
            device.deactivated_at = now
        device.is_active = False
        device.deactivation_reason = (
            f"permission_{body.permission.value}" if body.permission != PermissionState.granted else "no_token"
        )
    db.commit()
    return {"active": device.is_active}


@router.delete("/devices/{installation_id}", status_code=204, summary="Stop notifications for this installation")
def unregister_device(installation_id: str, request: Request, db: Session = Depends(get_db)):
    limiter.hit(f"devices:{client_ip(request)}", limit=30, window_seconds=60)
    device = db.scalar(select(PushDevice).where(PushDevice.installation_id == installation_id))
    if device and device.is_active:
        device.is_active = False
        device.deactivated_at = utcnow()
        device.deactivation_reason = "unregistered"
        db.commit()
    return Response(status_code=204)

