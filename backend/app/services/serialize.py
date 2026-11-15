"""Model → JSON-ready dict conversion shared by public and admin endpoints.

Public payloads never include internal notes, audit data, push tokens or storage credentials.
"""

from app.core.text import MONTHS_TR, WEEKDAYS_TR, to_local
from app.models import (
    CREDIT_ROLE_LABELS_TR,
    Article,
    CreditRole,
    Performance,
    PerformanceStatus,
    Production,
    Venue,
)
from app.schemas.common import youtube_id
from app.services.media import image_dict


def excerpt(text: str | None, limit: int = 180) -> str | None:
    if not text:
        return None
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat[:limit].rsplit(" ", 1)[0].rstrip(",;:—-")
    return cut + "…"


def duration_label(p: Production) -> str | None:
    parts = []
    if p.duration_minutes:
        parts.append(f"{p.duration_minutes} dakika")
    if p.act_count:
        parts.append(f"{p.act_count} perde")
    if parts:
        return " · ".join(parts)
    return p.duration_text


def credit_name(p: Production, role: CreditRole) -> str | None:
    names = [c.name for c in p.credits if c.role == role]
    return ", ".join(names) if names else None


def local_time_fields(dt, tz: str) -> dict:
    d = to_local(dt, tz)
    return {
        "local_iso": d.isoformat(),
        "local_date": f"{d.day} {MONTHS_TR[d.month - 1]} {d.year}",
        "local_day": d.day,
        "local_month": MONTHS_TR[d.month - 1],
        "local_year": d.year,
        "local_weekday": WEEKDAYS_TR[d.weekday()],
        "local_time": d.strftime("%H:%M"),
    }


def venue_public(v: Venue) -> dict:
    return {
        "id": str(v.id),
        "name": v.name,
        "address": v.address,
        "district": v.district,
        "city": v.city,
        "maps_url": v.maps_url,
        "public_info": v.public_info,
        "timezone": v.timezone,
    }


def performance_public(perf: Performance, include_production: bool = True) -> dict:
    tz = perf.venue.timezone
    out = {
        "id": str(perf.id),
        "starts_at": perf.starts_at.isoformat(),
        **local_time_fields(perf.starts_at, tz),
        "status": perf.status.value,
        "is_cancelled": perf.status == PerformanceStatus.cancelled,
        "cancellation_note": perf.cancellation_note if perf.status == PerformanceStatus.cancelled else None,
        "is_rescheduled": perf.rescheduled_from is not None and perf.status == PerformanceStatus.scheduled,
        "rescheduled_from": perf.rescheduled_from.isoformat() if perf.rescheduled_from else None,
        "rescheduled_from_local": local_time_fields(perf.rescheduled_from, tz) if perf.rescheduled_from else None,
        "public_note": perf.public_note,
        "venue": venue_public(perf.venue),
    }
    if include_production:
        p = perf.production
        out["production"] = {
            "id": str(p.id),
            "slug": p.slug,
            "title": p.title,
            "genres": p.genres or [],
            "poster": image_dict(p.poster),
        }
    return out


def production_card(p: Production, next_perf: Performance | None = None, upcoming_count: int = 0) -> dict:
    return {
        "id": str(p.id),
        "slug": p.slug,
        "title": p.title,
        "genres": p.genres or [],
        "excerpt": p.short_description or excerpt(p.description),
        "poster": image_dict(p.poster),
        "author": credit_name(p, CreditRole.author),
        "director": credit_name(p, CreditRole.director),
        "duration_label": duration_label(p),
        "is_featured": p.is_featured,
        "on_stage": p.on_stage,
        "published_at": p.published_at.isoformat() if p.published_at else None,
        "upcoming_count": upcoming_count,
        "next_performance": performance_public(next_perf, include_production=False) if next_perf else None,
    }


def production_detail(p: Production, performances: list[Performance]) -> dict:
    scheduled = [x for x in performances if x.status == PerformanceStatus.scheduled]
    return {
        **production_card(p, scheduled[0] if scheduled else None, len(scheduled)),
        "short_description": p.short_description,
        "description": p.description,
        "duration_minutes": p.duration_minutes,
        "act_count": p.act_count,
        "duration_text": p.duration_text,
        "credits": [
            {
                "role": c.role.value,
                "label": c.role_label or CREDIT_ROLE_LABELS_TR[c.role],
                "name": c.name,
            }
            for c in p.credits
        ],
        "gallery": [{**image_dict(img.media), "caption": img.caption} for img in p.images],
        "videos": [
            {"url": v.url, "title": v.title, "youtube_id": youtube_id(v.url)} for v in p.videos
        ],
        "performances": [performance_public(x, include_production=False) for x in performances],
    }


def article_public(a: Article, full: bool = False) -> dict:
    out = {
        "id": str(a.id),
        "slug": a.slug,
        "title": a.title,
        "excerpt": excerpt(a.body, 200),
        "image": image_dict(a.image),
        "published_at": a.published_at.isoformat() if a.published_at else None,
        "published_local": local_time_fields(a.published_at, "Europe/Istanbul") if a.published_at else None,
    }
    if full:
        out["body"] = a.body
    return out
