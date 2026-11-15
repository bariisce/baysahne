"""Venues and performances (admin)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import client_ip, require_editor
from app.core.errors import AppError, bad_request, conflict, not_found
from app.core.text import utcnow
from app.db import get_db
from app.models import AdminUser, Performance, PerformanceStatus, Production, Venue, Visibility
from app.notifications import engine
from app.schemas.common import HttpsUrl, OptText, PageNo, PageSize, ReqText, StrictModel
from app.services import audit, serialize

router = APIRouter(prefix="/api/v1/admin", tags=["admin-schedule"])

CONFLICT_WINDOW = timedelta(hours=3)


# ---------------------------------------------------------------- venues


class VenueIn(StrictModel):
    name: ReqText = Field(max_length=200)
    address: OptText = Field(default=None, max_length=400)
    district: OptText = Field(default=None, max_length=100)
    city: OptText = Field(default=None, max_length=100)
    maps_url: HttpsUrl = Field(default=None, max_length=500)
    public_info: OptText = Field(default=None, max_length=5000)
    timezone: str = Field(default="Europe/Istanbul", max_length=64)
    is_active: bool = True

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        if v not in available_timezones():
            raise ValueError("Geçersiz saat dilimi.")
        return v


def venue_admin(v: Venue) -> dict:
    return {**serialize.venue_public(v), "is_active": v.is_active, "updated_at": v.updated_at.isoformat()}


@router.get("/venues", tags=["admin-venues"])
def list_venues(db: Session = Depends(get_db), _: AdminUser = Depends(require_editor)):
    return {"items": [venue_admin(v) for v in db.scalars(select(Venue).order_by(Venue.is_active.desc(), Venue.name))]}


@router.post("/venues", status_code=201, tags=["admin-venues"])
def create_venue(body: VenueIn, request: Request, db: Session = Depends(get_db),
                 user: AdminUser = Depends(require_editor)):
    v = Venue(**body.model_dump())
    db.add(v)
    db.flush()
    audit.record(db, user, "venue.create", entity_type="venue", entity_id=v.id, summary=f"Salon eklendi: {v.name}",
                 ip=client_ip(request))
    db.commit()
    return venue_admin(v)


@router.put("/venues/{venue_id}", tags=["admin-venues"])
def update_venue(venue_id: uuid.UUID, body: VenueIn, request: Request, db: Session = Depends(get_db),
                 user: AdminUser = Depends(require_editor)):
    v = db.get(Venue, venue_id)
    if not v:
        raise not_found("Salon bulunamadı.")
    for k, val in body.model_dump().items():
        setattr(v, k, val)
    audit.record(db, user, "venue.update", entity_type="venue", entity_id=v.id, summary=f"Salon güncellendi: {v.name}",
                 ip=client_ip(request))
    db.commit()
    return venue_admin(v)


@router.delete("/venues/{venue_id}", status_code=204, tags=["admin-venues"])
def delete_venue(venue_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                 user: AdminUser = Depends(require_editor)):
    v = db.get(Venue, venue_id)
    if not v:
        raise not_found("Salon bulunamadı.")
    if db.scalar(select(func.count()).select_from(Performance).where(Performance.venue_id == v.id)):
        raise conflict("venue_in_use", "Bu salonda kayıtlı temsiller var; silmek yerine pasif hâle getirin.")
    audit.record(db, user, "venue.delete", entity_type="venue", entity_id=v.id, summary=f"Salon silindi: {v.name}",
                 ip=client_ip(request))
    db.delete(v)
    db.commit()


# ---------------------------------------------------------------- performances


def _local_format(v: str | None) -> str | None:
    if v is None:
        return v
    try:
        datetime.strptime(v, "%Y-%m-%dT%H:%M")
    except ValueError as e:
        raise ValueError("Tarih ve saat YYYY-AA-GGTSS:DD biçiminde olmalıdır.") from e
    return v


class LocalDateTime(StrictModel):
    starts_at_local: str = Field(description="Venue-local wall time, 'YYYY-MM-DDTHH:MM'", max_length=16)

    _fmt = field_validator("starts_at_local")(classmethod(lambda cls, v: _local_format(v)))


class PerformanceIn(LocalDateTime):
    production_id: uuid.UUID
    venue_id: uuid.UUID
    visibility: Visibility = Visibility.draft
    public_note: OptText = Field(default=None, max_length=500)
    internal_notes: OptText = Field(default=None, max_length=5000)
    allow_conflict: bool = False


class PerformancePatch(StrictModel):
    venue_id: uuid.UUID | None = None
    starts_at_local: str | None = Field(default=None, max_length=16)
    public_note: OptText = Field(default=None, max_length=500)
    internal_notes: OptText = Field(default=None, max_length=5000)
    allow_conflict: bool = False

    _fmt = field_validator("starts_at_local")(classmethod(lambda cls, v: _local_format(v)))


class RescheduleIn(LocalDateTime):
    notify: bool = True
    allow_conflict: bool = False


class CancelIn(StrictModel):
    cancellation_note: OptText = Field(default=None, max_length=500)
    notify: bool = True


def to_utc(local: str, tz: str) -> datetime:
    try:
        zone = ZoneInfo(tz)
    except ZoneInfoNotFoundError as e:
        raise bad_request("invalid_timezone", "Salonun saat dilimi geçersiz.") from e
    naive = datetime.strptime(local, "%Y-%m-%dT%H:%M")
    aware = naive.replace(tzinfo=zone)
    # Reject wall times that do not exist (DST gap) — round-tripping changes them.
    if aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != naive:
        raise bad_request("invalid_local_time", "Bu saat, saat dilimi değişikliği nedeniyle geçersiz.")
    return aware.astimezone(UTC)


def find_conflicts(db: Session, *, starts_at: datetime, venue_id, production_id, exclude_id=None) -> list[dict]:
    q = select(Performance).where(
        Performance.status == PerformanceStatus.scheduled,
        Performance.starts_at > starts_at - CONFLICT_WINDOW,
        Performance.starts_at < starts_at + CONFLICT_WINDOW,
        or_(Performance.venue_id == venue_id, Performance.production_id == production_id),
    )
    if exclude_id:
        q = q.where(Performance.id != exclude_id)
    out = []
    for other in db.scalars(q).unique():
        reason = "same_venue" if other.venue_id == venue_id else "same_production"
        out.append({
            "performance_id": str(other.id),
            "reason": reason,
            "message": ("Aynı salonda yakın saatte başka bir temsil var" if reason == "same_venue"
                        else "Bu oyunun yakın saatte başka bir salonda temsili var"),
            "production": other.production.title,
            "venue": other.venue.name,
            **serialize.local_time_fields(other.starts_at, other.venue.timezone),
        })
    return out


def _check_conflicts(db, *, starts_at, venue_id, production_id, exclude_id, allow: bool) -> list[dict]:
    found = find_conflicts(db, starts_at=starts_at, venue_id=venue_id, production_id=production_id,
                           exclude_id=exclude_id)
    if found and not allow:
        raise AppError(409, "schedule_conflict",
                       "Program çakışması var. Kontrol edip yine de kaydetmek istiyorsanız onaylayın.",
                       {"conflicts": found})
    return found


def perf_admin(p: Performance) -> dict:
    return {
        **serialize.performance_public(p),
        "visibility": p.visibility.value,
        "internal_notes": p.internal_notes,
        "first_published_at": p.first_published_at.isoformat() if p.first_published_at else None,
        "reschedule_count": p.reschedule_count,
        "cancelled_at": p.cancelled_at.isoformat() if p.cancelled_at else None,
        "production_status": p.production.status.value,
        "is_past": p.starts_at <= utcnow(),
        "updated_at": p.updated_at.isoformat(),
    }


def _get_perf(db: Session, pid: uuid.UUID) -> Performance:
    p = db.get(Performance, pid)
    if not p:
        raise not_found("Temsil bulunamadı.")
    return p


def _venue(db: Session, vid: uuid.UUID) -> Venue:
    v = db.get(Venue, vid)
    if not v:
        raise bad_request("venue_not_found", "Salon bulunamadı.")
    return v


@router.get("/performances", tags=["admin-performances"])
def list_performances(
    production_id: uuid.UUID | None = None,
    scope: Annotated[str, Query(pattern="^(upcoming|past|all)$")] = "upcoming",
    status: PerformanceStatus | None = None,
    page: PageNo = 1,
    page_size: PageSize = 50,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_editor),
):
    now = utcnow()
    q = select(Performance)
    if production_id:
        q = q.where(Performance.production_id == production_id)
    if status:
        q = q.where(Performance.status == status)
    if scope == "upcoming":
        q = q.where(Performance.starts_at > now).order_by(Performance.starts_at)
    elif scope == "past":
        q = q.where(Performance.starts_at <= now).order_by(Performance.starts_at.desc())
    else:
        q = q.order_by(Performance.starts_at.desc())
    total = db.scalar(select(func.count()).select_from(q.order_by(None).subquery()))
    rows = db.scalars(q.offset((page - 1) * page_size).limit(page_size)).unique().all()
    return {"items": [perf_admin(p) for p in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/performances", status_code=201, tags=["admin-performances"])
def create_performance(body: PerformanceIn, request: Request, db: Session = Depends(get_db),
                       user: AdminUser = Depends(require_editor)):
    production = db.get(Production, body.production_id)
    if not production:
        raise bad_request("production_not_found", "Oyun bulunamadı.")
    venue = _venue(db, body.venue_id)
    starts_at = to_utc(body.starts_at_local, venue.timezone)
    if starts_at <= utcnow():
        raise bad_request("past_datetime", "Geçmiş bir tarih ve saat için temsil oluşturulamaz.")
    conflicts = _check_conflicts(db, starts_at=starts_at, venue_id=venue.id, production_id=production.id,
                                 exclude_id=None, allow=body.allow_conflict)
    now = utcnow()
    perf = Performance(
        production_id=production.id, venue_id=venue.id, starts_at=starts_at, visibility=body.visibility,
        public_note=body.public_note, internal_notes=body.internal_notes, updated_by_id=user.id,
        first_published_at=now if body.visibility == Visibility.published else None,
    )
    db.add(perf)
    db.flush()
    audit.record(db, user, "performance.create", entity_type="performance", entity_id=perf.id,
                 summary=f"Temsil eklendi: {production.title} — {body.starts_at_local}",
                 details={"conflicts_acknowledged": len(conflicts)}, ip=client_ip(request))
    db.commit()
    engine.plan_reminders(db)
    db.commit()
    db.refresh(perf)
    return {**perf_admin(perf), "warnings": _warnings(perf)}


def _warnings(perf: Performance) -> list[str]:
    w = []
    if perf.production.status.value != "published":
        w.append("Oyun yayında olmadığı için bu temsil uygulamada görünmez.")
    if perf.visibility == Visibility.draft:
        w.append("Temsil taslak durumda; yayınlanana kadar uygulamada görünmez.")
    return w


@router.get("/performances/{performance_id}", tags=["admin-performances"])
def get_performance(performance_id: uuid.UUID, db: Session = Depends(get_db), _: AdminUser = Depends(require_editor)):
    p = _get_perf(db, performance_id)
    return {**perf_admin(p), "warnings": _warnings(p)}


@router.patch("/performances/{performance_id}", tags=["admin-performances"])
def update_performance(performance_id: uuid.UUID, body: PerformancePatch, request: Request,
                       db: Session = Depends(get_db), user: AdminUser = Depends(require_editor)):
    p = _get_perf(db, performance_id)
    data = body.model_dump(exclude_unset=True)
    allow = data.pop("allow_conflict", False)
    venue = _venue(db, data["venue_id"]) if data.get("venue_id") else p.venue
    new_start = p.starts_at
    if data.get("starts_at_local"):
        new_start = to_utc(data.pop("starts_at_local"), venue.timezone)
        if new_start != p.starts_at and p.first_published_at:
            raise conflict("use_reschedule",
                           "Yayınlanmış bir temsilin tarihi 'Ertele / Tarih değiştir' işlemiyle değiştirilmelidir.")
        if new_start <= utcnow():
            raise bad_request("past_datetime", "Geçmiş bir tarih ve saat seçilemez.")
    else:
        data.pop("starts_at_local", None)
    if new_start != p.starts_at or venue.id != p.venue_id:
        _check_conflicts(db, starts_at=new_start, venue_id=venue.id, production_id=p.production_id,
                         exclude_id=p.id, allow=allow)
    p.starts_at = new_start
    if "venue_id" in data:
        p.venue_id = data.pop("venue_id")
    for k, v in data.items():
        setattr(p, k, v)
    p.updated_by_id = user.id
    audit.record(db, user, "performance.update", entity_type="performance", entity_id=p.id,
                 summary=f"Temsil güncellendi: {p.production.title}", details={"fields": sorted(body.model_fields_set)},
                 ip=client_ip(request))
    db.commit()
    engine.cancel_stale_jobs(db)
    engine.plan_reminders(db)
    db.commit()
    db.refresh(p)
    return {**perf_admin(p), "warnings": _warnings(p)}


@router.post("/performances/{performance_id}/publish", tags=["admin-performances"])
def publish_performance(performance_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                        user: AdminUser = Depends(require_editor)):
    p = _get_perf(db, performance_id)
    if p.status == PerformanceStatus.cancelled:
        raise conflict("cancelled", "İptal edilmiş bir temsil yayınlanamaz.")
    if p.starts_at <= utcnow():
        raise bad_request("past_datetime", "Geçmiş bir temsil yayınlanamaz.")
    p.visibility = Visibility.published
    p.first_published_at = p.first_published_at or utcnow()
    audit.record(db, user, "performance.publish", entity_type="performance", entity_id=p.id,
                 summary=f"Temsil yayınlandı: {p.production.title}", ip=client_ip(request))
    db.commit()
    engine.plan_reminders(db)
    db.commit()
    return {**perf_admin(p), "warnings": _warnings(p)}


@router.post("/performances/{performance_id}/unpublish", tags=["admin-performances"])
def unpublish_performance(performance_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                          user: AdminUser = Depends(require_editor)):
    p = _get_perf(db, performance_id)
    p.visibility = Visibility.draft
    engine.cancel_stale_jobs(db)
    audit.record(db, user, "performance.unpublish", entity_type="performance", entity_id=p.id,
                 summary=f"Temsil yayından kaldırıldı: {p.production.title}", ip=client_ip(request))
    db.commit()
    return {**perf_admin(p), "warnings": _warnings(p)}


@router.post("/performances/{performance_id}/cancel", tags=["admin-performances"])
def cancel_performance(performance_id: uuid.UUID, body: CancelIn, request: Request, db: Session = Depends(get_db),
                       user: AdminUser = Depends(require_editor)):
    p = _get_perf(db, performance_id)
    if p.status == PerformanceStatus.cancelled:
        raise conflict("already_cancelled", "Temsil zaten iptal edilmiş.")
    if p.starts_at <= utcnow():
        raise bad_request("past_performance", "Geçmiş bir temsil iptal edilemez.")
    p.status = PerformanceStatus.cancelled
    p.cancelled_at = utcnow()
    p.cancellation_note = body.cancellation_note
    p.updated_by_id = user.id
    db.flush()
    job = engine.on_performance_cancelled(db, p, user.id) if body.notify else None
    if not body.notify:
        engine.cancel_pending_for_performance(db, p.id, "performance_cancelled")
    audit.record(db, user, "performance.cancel", entity_type="performance", entity_id=p.id,
                 summary=f"Temsil iptal edildi: {p.production.title}",
                 details={"notify": body.notify, "notification_job": str(job.id) if job else None},
                 ip=client_ip(request))
    db.commit()
    return {**perf_admin(p), "notification_job_id": str(job.id) if job else None, "warnings": _warnings(p)}


@router.post("/performances/{performance_id}/restore", tags=["admin-performances"],
             summary="Undo a cancellation (future performances only)")
def restore_performance(performance_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                        user: AdminUser = Depends(require_editor)):
    p = _get_perf(db, performance_id)
    if p.status != PerformanceStatus.cancelled:
        raise conflict("not_cancelled", "Temsil iptal edilmiş değil.")
    if p.starts_at <= utcnow():
        raise bad_request("past_performance", "Geçmiş bir temsil yeniden etkinleştirilemez.")
    _check_conflicts(db, starts_at=p.starts_at, venue_id=p.venue_id, production_id=p.production_id,
                     exclude_id=p.id, allow=False)
    p.status = PerformanceStatus.scheduled
    p.cancelled_at = None
    p.cancellation_note = None
    engine.cancel_stale_jobs(db)
    audit.record(db, user, "performance.restore", entity_type="performance", entity_id=p.id,
                 summary=f"İptal geri alındı: {p.production.title}", ip=client_ip(request))
    db.commit()
    engine.plan_reminders(db)
    db.commit()
    return {**perf_admin(p), "warnings": _warnings(p)}


@router.post("/performances/{performance_id}/reschedule", tags=["admin-performances"])
def reschedule_performance(performance_id: uuid.UUID, body: RescheduleIn, request: Request,
                           db: Session = Depends(get_db), user: AdminUser = Depends(require_editor)):
    p = _get_perf(db, performance_id)
    if p.status == PerformanceStatus.cancelled:
        raise conflict("cancelled", "İptal edilmiş bir temsilin tarihi değiştirilemez; önce iptali geri alın.")
    new_start = to_utc(body.starts_at_local, p.venue.timezone)
    if new_start <= utcnow():
        raise bad_request("past_datetime", "Geçmiş bir tarih ve saat seçilemez.")
    if new_start == p.starts_at:
        raise bad_request("same_datetime", "Yeni tarih ve saat mevcut olanla aynı.")
    _check_conflicts(db, starts_at=new_start, venue_id=p.venue_id, production_id=p.production_id,
                     exclude_id=p.id, allow=body.allow_conflict)
    old = p.starts_at
    p.rescheduled_from = old
    p.rescheduled_at = utcnow()
    p.reschedule_count += 1
    p.starts_at = new_start
    p.updated_by_id = user.id
    db.flush()
    job = engine.on_performance_rescheduled(db, p, user.id) if body.notify else None
    if not body.notify:
        engine.cancel_stale_jobs(db)
    audit.record(db, user, "performance.reschedule", entity_type="performance", entity_id=p.id,
                 summary=f"Temsil tarihi değişti: {p.production.title}",
                 details={"from": old.isoformat(), "to": new_start.isoformat(), "notify": body.notify,
                          "notification_job": str(job.id) if job else None},
                 ip=client_ip(request))
    db.commit()
    engine.plan_reminders(db)
    db.commit()
    return {**perf_admin(p), "notification_job_id": str(job.id) if job else None, "warnings": _warnings(p)}


@router.delete("/performances/{performance_id}", status_code=204, tags=["admin-performances"])
def delete_performance(performance_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                       user: AdminUser = Depends(require_editor)):
    p = _get_perf(db, performance_id)
    if p.first_published_at:
        raise conflict("cannot_delete", "Yayınlanmış bir temsil silinemez; iptal edin.")
    engine.cancel_pending_for_performance(db, p.id, "performance_deleted")
    audit.record(db, user, "performance.delete", entity_type="performance", entity_id=p.id,
                 summary=f"Taslak temsil silindi: {p.production.title}", ip=client_ip(request))
    db.delete(p)
    db.commit()
