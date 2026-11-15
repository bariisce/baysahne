import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import client_ip, require_editor
from app.core.errors import bad_request, conflict, not_found
from app.core.text import slugify, utcnow
from app.db import get_db
from app.models import (
    AdminUser,
    CreditRole,
    MediaAsset,
    Performance,
    Production,
    ProductionCredit,
    ProductionImage,
    ProductionVideo,
    PublicationStatus,
)
from app.notifications import engine
from app.schemas.common import HttpsUrl, OptText, PageNo, PageSize, ReqText, Slug, StrictModel
from app.services import audit, queries, serialize

router = APIRouter(prefix="/api/v1/admin/productions", tags=["admin-productions"])


class CreditIn(StrictModel):
    role: CreditRole
    role_label: OptText = Field(default=None, max_length=80)
    name: ReqText = Field(max_length=200)


class VideoIn(StrictModel):
    url: HttpsUrl = Field(max_length=500)
    title: OptText = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _url_required(self):
        if not self.url:
            raise ValueError("Video bağlantısı zorunludur.")
        return self


class ProductionIn(StrictModel):
    title: ReqText = Field(max_length=200)
    slug: Slug = None
    short_description: OptText = Field(default=None, max_length=400)
    description: OptText = Field(default=None, max_length=20000)
    genres: list[Annotated[str, Field(min_length=1, max_length=60)]] = Field(default_factory=list, max_length=10)
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    act_count: int | None = Field(default=None, ge=1, le=20)
    duration_text: OptText = Field(default=None, max_length=120)
    is_featured: bool = False
    on_stage: bool = False
    sort_order: int = Field(default=0, ge=-10000, le=10000)
    home_order: int | None = Field(default=None, ge=1, le=1000)
    credits: list[CreditIn] = Field(default_factory=list, max_length=200)
    videos: list[VideoIn] = Field(default_factory=list, max_length=20)


class ProductionPatch(StrictModel):
    """Partial update: only provided fields change."""

    title: ReqText | None = Field(default=None, max_length=200)
    slug: Slug = None
    short_description: OptText = Field(default=None, max_length=400)
    description: OptText = Field(default=None, max_length=20000)
    genres: list[Annotated[str, Field(min_length=1, max_length=60)]] | None = Field(default=None, max_length=10)
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    act_count: int | None = Field(default=None, ge=1, le=20)
    duration_text: OptText = Field(default=None, max_length=120)
    is_featured: bool | None = None
    on_stage: bool | None = None
    sort_order: int | None = Field(default=None, ge=-10000, le=10000)
    # Sent as null to take the production off the home screen's repertoire strip.
    home_order: int | None = Field(default=None, ge=1, le=1000)
    credits: list[CreditIn] | None = Field(default=None, max_length=200)
    videos: list[VideoIn] | None = Field(default=None, max_length=20)


class PublishIn(StrictModel):
    notify: bool = Field(default=False, description="Send the 'new production' push (first publication only)")


class PosterIn(StrictModel):
    media_id: uuid.UUID


class GalleryAddIn(StrictModel):
    media_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)


class GalleryOrderIn(StrictModel):
    image_ids: list[uuid.UUID] = Field(max_length=200)


class CaptionIn(StrictModel):
    caption: OptText = Field(default=None, max_length=300)


def completeness(p: Production) -> list[dict]:
    issues = []
    if not p.poster_id:
        issues.append({"field": "poster", "message": "Afiş yok"})
    if not p.description:
        issues.append({"field": "description", "message": "Açıklama (hikâye) yok"})
    if not any(c.role == CreditRole.author for c in p.credits):
        issues.append({"field": "author", "message": "Yazar bilgisi yok"})
    if not any(c.role == CreditRole.director for c in p.credits):
        issues.append({"field": "director", "message": "Yönetmen bilgisi yok"})
    if not (p.duration_minutes or p.act_count or p.duration_text):
        issues.append({"field": "duration", "message": "Süre bilgisi yok"})
    if not p.genres:
        issues.append({"field": "genres", "message": "Tür bilgisi yok"})
    return issues


def production_admin(db: Session, p: Production) -> dict:
    perf_counts = dict(
        db.execute(
            select(Performance.status, func.count())
            .where(Performance.production_id == p.id, Performance.starts_at > utcnow())
            .group_by(Performance.status)
        ).all()
    )
    return {
        **serialize.production_detail(p, []),
        "status": p.status.value,
        "sort_order": p.sort_order,
        "home_order": p.home_order,
        "first_published_at": p.first_published_at.isoformat() if p.first_published_at else None,
        "archived_at": p.archived_at.isoformat() if p.archived_at else None,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
        "import_key": p.import_key,
        "gallery": [
            {**(serialize.image_dict(img.media) or {}), "image_id": str(img.id), "caption": img.caption}
            for img in p.images
        ],
        "issues": completeness(p),
        "upcoming_performances": {k.value: v for k, v in perf_counts.items()},
    }


def _get(db: Session, production_id: uuid.UUID) -> Production:
    p = db.get(Production, production_id)
    if not p:
        raise not_found("Oyun bulunamadı.")
    return p


def _unique_slug(db: Session, base: str, exclude_id=None) -> str:
    slug, n = base, 2
    while db.scalar(select(Production.id).where(Production.slug == slug, Production.id != exclude_id)):
        slug, n = f"{base}-{n}", n + 1
    return slug


def _apply(db: Session, p: Production, data: dict) -> None:
    credits = data.pop("credits", None)
    videos = data.pop("videos", None)
    if "genres" in data and data["genres"] is not None:
        seen, genres = set(), []
        for g in (x.strip() for x in data["genres"]):
            if g and g.lower() not in seen:
                seen.add(g.lower())
                genres.append(g)
        data["genres"] = genres
    if data.get("slug") and db.scalar(
        select(Production.id).where(Production.slug == data["slug"], Production.id != p.id)
    ):
        raise conflict("slug_taken", "Bu kısa ad başka bir oyunda kullanılıyor.")
    for k, v in data.items():
        setattr(p, k, v)
    if credits is not None:
        for c in credits:
            if c["role"] == CreditRole.other and not c.get("role_label"):
                raise bad_request("credit_label_required", "'Diğer' görevler için görev adı yazın.")
        p.credits = [ProductionCredit(position=i, **c) for i, c in enumerate(credits)]
    if videos is not None:
        p.videos = [ProductionVideo(position=i, **v) for i, v in enumerate(videos)]


@router.get("")
def list_productions(
    q: Annotated[str | None, Query(max_length=100)] = None,
    status: PublicationStatus | None = None,
    page: PageNo = 1,
    page_size: PageSize = 50,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_editor),
):
    stmt = select(Production)
    if status:
        stmt = stmt.where(Production.status == status)
    items = list(db.scalars(stmt).unique())
    if q:
        needle = queries.fold(q)
        items = [p for p in items if needle in queries.fold(p.title)]
    items.sort(key=lambda p: (p.status != PublicationStatus.published, p.sort_order, queries.fold(p.title)))
    total = len(items)
    items = items[(page - 1) * page_size: page * page_size]
    return {
        "items": [
            {
                "id": str(p.id), "slug": p.slug, "title": p.title, "status": p.status.value,
                "genres": p.genres or [], "is_featured": p.is_featured, "on_stage": p.on_stage,
                "poster": serialize.image_dict(p.poster), "updated_at": p.updated_at.isoformat(),
                "issues": completeness(p),
            }
            for p in items
        ],
        "total": total, "page": page, "page_size": page_size,
    }


@router.post("", status_code=201)
def create_production(body: ProductionIn, request: Request, db: Session = Depends(get_db),
                      user: AdminUser = Depends(require_editor)):
    data = body.model_dump()
    slug = data.pop("slug") or _unique_slug(db, slugify(body.title))
    p = Production(slug=slug, status=PublicationStatus.draft, updated_by_id=user.id, title=body.title)
    db.add(p)
    _apply(db, p, data)
    db.flush()
    audit.record(db, user, "production.create", entity_type="production", entity_id=p.id,
                 summary=f"Oyun oluşturuldu: {p.title}", ip=client_ip(request))
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise conflict("slug_taken", "Bu kısa ad başka bir oyunda kullanılıyor.") from e
    return production_admin(db, p)


@router.get("/{production_id}")
def get_production(production_id: uuid.UUID, db: Session = Depends(get_db), _: AdminUser = Depends(require_editor)):
    return production_admin(db, _get(db, production_id))


@router.get("/{production_id}/preview", summary="Render exactly what the app would show, regardless of status")
def preview(production_id: uuid.UUID, db: Session = Depends(get_db), _: AdminUser = Depends(require_editor)):
    p = _get(db, production_id)
    perfs = db.scalars(
        select(Performance).where(Performance.production_id == p.id, Performance.starts_at > utcnow())
        .order_by(Performance.starts_at)
    ).unique().all()
    return serialize.production_detail(p, list(perfs))


@router.patch("/{production_id}")
def update_production(production_id: uuid.UUID, body: ProductionPatch, request: Request,
                      db: Session = Depends(get_db), user: AdminUser = Depends(require_editor)):
    p = _get(db, production_id)
    data = body.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is None:
        raise bad_request("title_required", "Oyun adı boş bırakılamaz.")
    if "slug" in data and data["slug"] is None:
        data.pop("slug")
    _apply(db, p, data)
    p.updated_by_id = user.id
    audit.record(db, user, "production.update", entity_type="production", entity_id=p.id,
                 summary=f"Oyun güncellendi: {p.title}", details={"fields": sorted(data.keys())},
                 ip=client_ip(request))
    db.commit()
    db.refresh(p)
    return production_admin(db, p)


@router.post("/{production_id}/publish")
def publish(production_id: uuid.UUID, body: PublishIn, request: Request, db: Session = Depends(get_db),
            user: AdminUser = Depends(require_editor)):
    p = _get(db, production_id)
    if p.status == PublicationStatus.published:
        raise conflict("already_published", "Oyun zaten yayında.")
    now = utcnow()
    first_time = p.first_published_at is None
    p.status = PublicationStatus.published
    p.published_at = now
    p.archived_at = None
    p.first_published_at = p.first_published_at or now
    p.updated_by_id = user.id
    job = None
    if body.notify and first_time:
        job = engine.on_production_published(db, p, user.id)
    audit.record(db, user, "production.publish", entity_type="production", entity_id=p.id,
                 summary=f"Oyun yayınlandı: {p.title}",
                 details={"notify": body.notify, "notification_job": str(job.id) if job else None},
                 ip=client_ip(request))
    db.commit()
    engine.plan_reminders(db)
    db.commit()
    return {**production_admin(db, p), "notification_job_id": str(job.id) if job else None,
            "notification_skipped_reason": None if job or not body.notify else (
                "already_published_before" if not first_time else "category_disabled_or_duplicate")}


@router.post("/{production_id}/unpublish")
def unpublish(production_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
              user: AdminUser = Depends(require_editor)):
    p = _get(db, production_id)
    if p.status != PublicationStatus.published:
        raise conflict("not_published", "Oyun yayında değil.")
    p.status = PublicationStatus.draft
    p.updated_by_id = user.id
    engine.cancel_stale_jobs(db)
    audit.record(db, user, "production.unpublish", entity_type="production", entity_id=p.id,
                 summary=f"Oyun yayından kaldırıldı: {p.title}", ip=client_ip(request))
    db.commit()
    return production_admin(db, p)


@router.post("/{production_id}/archive")
def archive(production_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
            user: AdminUser = Depends(require_editor)):
    p = _get(db, production_id)
    if p.status == PublicationStatus.archived:
        raise conflict("already_archived", "Oyun zaten arşivde.")
    p.status = PublicationStatus.archived
    p.archived_at = utcnow()
    p.updated_by_id = user.id
    engine.cancel_stale_jobs(db)
    audit.record(db, user, "production.archive", entity_type="production", entity_id=p.id,
                 summary=f"Oyun arşivlendi: {p.title}", ip=client_ip(request))
    db.commit()
    return production_admin(db, p)


@router.post("/{production_id}/restore", summary="Move an archived production back to draft")
def restore(production_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
            user: AdminUser = Depends(require_editor)):
    p = _get(db, production_id)
    if p.status != PublicationStatus.archived:
        raise conflict("not_archived", "Oyun arşivde değil.")
    p.status = PublicationStatus.draft
    p.archived_at = None
    audit.record(db, user, "production.restore", entity_type="production", entity_id=p.id,
                 summary=f"Oyun arşivden çıkarıldı: {p.title}", ip=client_ip(request))
    db.commit()
    return production_admin(db, p)


@router.delete("/{production_id}", status_code=204)
def delete_production(production_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                      user: AdminUser = Depends(require_editor)):
    p = _get(db, production_id)
    has_perf = db.scalar(select(func.count()).select_from(Performance).where(Performance.production_id == p.id))
    if p.first_published_at or has_perf:
        raise conflict("cannot_delete",
                       "Yayınlanmış veya temsili olan bir oyun silinemez; geçmişi korumak için arşivleyin.")
    audit.record(db, user, "production.delete", entity_type="production", entity_id=p.id,
                 summary=f"Taslak oyun silindi: {p.title}", ip=client_ip(request))
    db.delete(p)
    db.commit()


# ---------------------------------------------------------------- poster & gallery


def _media(db: Session, media_id: uuid.UUID) -> MediaAsset:
    m = db.get(MediaAsset, media_id)
    if not m:
        raise not_found("Görsel bulunamadı.")
    return m


@router.put("/{production_id}/poster")
def set_poster(production_id: uuid.UUID, body: PosterIn, request: Request, db: Session = Depends(get_db),
               user: AdminUser = Depends(require_editor)):
    p = _get(db, production_id)
    _media(db, body.media_id)
    previous = p.poster_id
    p.poster_id = body.media_id
    p.updated_by_id = user.id
    audit.record(db, user, "production.poster_set", entity_type="production", entity_id=p.id,
                 summary=f"Afiş değiştirildi: {p.title}",
                 details={"media_id": str(body.media_id), "previous": str(previous) if previous else None},
                 ip=client_ip(request))
    db.commit()
    db.refresh(p)
    return production_admin(db, p)


@router.delete("/{production_id}/poster")
def remove_poster(production_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                  user: AdminUser = Depends(require_editor)):
    p = _get(db, production_id)
    p.poster_id = None
    audit.record(db, user, "production.poster_removed", entity_type="production", entity_id=p.id,
                 summary=f"Afiş kaldırıldı: {p.title}", ip=client_ip(request))
    db.commit()
    db.refresh(p)
    return production_admin(db, p)


@router.post("/{production_id}/images")
def add_images(production_id: uuid.UUID, body: GalleryAddIn, request: Request, db: Session = Depends(get_db),
               user: AdminUser = Depends(require_editor)):
    p = _get(db, production_id)
    existing = {img.media_id for img in p.images}
    pos = max((img.position for img in p.images), default=-1) + 1
    added = 0
    for mid in body.media_ids:
        _media(db, mid)
        if mid in existing:
            continue
        p.images.append(ProductionImage(media_id=mid, position=pos))
        existing.add(mid)
        pos += 1
        added += 1
    audit.record(db, user, "production.gallery_add", entity_type="production", entity_id=p.id,
                 summary=f"Galeriye {added} görsel eklendi: {p.title}", ip=client_ip(request))
    db.commit()
    db.refresh(p)
    return production_admin(db, p)


@router.put("/{production_id}/images/order")
def reorder_images(production_id: uuid.UUID, body: GalleryOrderIn, request: Request,
                   db: Session = Depends(get_db), user: AdminUser = Depends(require_editor)):
    p = _get(db, production_id)
    current = {img.id: img for img in p.images}
    if set(body.image_ids) != set(current):
        raise bad_request("order_mismatch", "Sıralama listesi galerideki görsellerle eşleşmiyor. Sayfayı yenileyin.")
    for i, iid in enumerate(body.image_ids):
        current[iid].position = i
    audit.record(db, user, "production.gallery_reorder", entity_type="production", entity_id=p.id,
                 summary=f"Galeri sırası değişti: {p.title}", ip=client_ip(request))
    db.commit()
    db.expire(p)
    return production_admin(db, p)


@router.patch("/{production_id}/images/{image_id}")
def caption_image(production_id: uuid.UUID, image_id: uuid.UUID, body: CaptionIn, db: Session = Depends(get_db),
                  user: AdminUser = Depends(require_editor)):
    p = _get(db, production_id)
    img = next((i for i in p.images if i.id == image_id), None)
    if not img:
        raise not_found("Görsel bulunamadı.")
    img.caption = body.caption
    db.commit()
    return production_admin(db, p)


@router.delete("/{production_id}/images/{image_id}")
def remove_image(production_id: uuid.UUID, image_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                 user: AdminUser = Depends(require_editor)):
    p = _get(db, production_id)
    img = next((i for i in p.images if i.id == image_id), None)
    if not img:
        raise not_found("Görsel bulunamadı.")
    p.images.remove(img)
    audit.record(db, user, "production.gallery_remove", entity_type="production", entity_id=p.id,
                 summary=f"Galeriden görsel kaldırıldı: {p.title}", details={"media_id": str(img.media_id)},
                 ip=client_ip(request))
    db.commit()
    db.refresh(p)
    return production_admin(db, p)
