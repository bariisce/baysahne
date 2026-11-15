"""Dashboard, staff management, notification administration, organisation profile, legal texts, audit log."""

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.admin.productions import completeness
from app.api.deps import client_ip, require_admin, require_editor
from app.config import get_settings
from app.core.errors import AppError, bad_request, conflict, not_found
from app.core.text import utcnow
from app.db import get_db
from app.models import (
    AdminInvitation,
    AdminRole,
    AdminUser,
    Article,
    AuditLog,
    DevicePlatform,
    JobStatus,
    LegalDocument,
    MediaAsset,
    NotificationCategory,
    NotificationCategorySetting,
    NotificationDelivery,
    NotificationJob,
    OrganizationProfile,
    Performance,
    PerformanceStatus,
    Production,
    PublicationStatus,
    PushDevice,
    Visibility,
)
from app.notifications import engine, templates
from app.schemas.common import HttpsUrl, OptText, PageNo, PageSize, ReqText, StrictModel
from app.services import audit, serialize
from app.services import auth as auth_service
from app.services.media import image_dict

router = APIRouter(prefix="/api/v1/admin", tags=["admin-system"])


# ---------------------------------------------------------------- dashboard


@router.get("/dashboard", tags=["admin-dashboard"])
def dashboard(db: Session = Depends(get_db), _: AdminUser = Depends(require_editor)):
    now = utcnow()
    by_status = dict(db.execute(select(Production.status, func.count()).group_by(Production.status)).all())
    productions = db.scalars(select(Production).where(Production.status != PublicationStatus.archived)).unique().all()
    incomplete = [
        {"id": str(p.id), "title": p.title, "status": p.status.value, "issues": completeness(p)}
        for p in productions if completeness(p)
    ]
    upcoming_q = select(Performance).where(
        Performance.starts_at > now, Performance.status == PerformanceStatus.scheduled
    )
    upcoming_total = db.scalar(select(func.count()).select_from(upcoming_q.subquery()))
    upcoming_public = db.scalar(select(func.count()).select_from(
        upcoming_q.join(Production, Production.id == Performance.production_id).where(
            Performance.visibility == Visibility.published, Production.status == PublicationStatus.published
        ).subquery()))
    next_perfs = db.scalars(upcoming_q.order_by(Performance.starts_at).limit(5)).unique().all()
    draft_perfs = db.scalar(select(func.count()).select_from(
        upcoming_q.where(Performance.visibility == Visibility.draft).subquery()))
    recent = db.scalars(
        select(AuditLog).where(AuditLog.entity_type.in_(["production", "performance", "article", "venue"]))
        .order_by(AuditLog.created_at.desc()).limit(8)
    ).all()
    failed_jobs = db.scalar(select(func.count()).select_from(NotificationJob).where(
        NotificationJob.status == JobStatus.failed, NotificationJob.updated_at > now - timedelta(days=7)))
    pending_jobs = db.scalar(select(func.count()).select_from(NotificationJob).where(
        NotificationJob.status == JobStatus.pending))
    active_devices = db.scalar(select(func.count()).select_from(PushDevice).where(PushDevice.is_active.is_(True)))
    draft_articles = db.scalar(select(func.count()).select_from(Article).where(Article.status == Visibility.draft))

    tasks = []
    if not upcoming_public:
        tasks.append({"kind": "no_schedule", "message": "Uygulamada görünen yaklaşan temsil yok. Program ekleyin."})
    if draft_perfs:
        tasks.append({"kind": "draft_performances", "message": f"{draft_perfs} yaklaşan temsil taslak durumda."})
    drafts = by_status.get(PublicationStatus.draft, 0)
    if drafts:
        tasks.append({"kind": "draft_productions", "message": f"{drafts} oyun taslak durumda."})
    if incomplete:
        tasks.append({"kind": "incomplete", "message": f"{len(incomplete)} oyunda eksik bilgi var."})
    if failed_jobs:
        tasks.append({"kind": "failed_notifications", "message": f"Son 7 günde {failed_jobs} bildirim gönderilemedi."})

    return {
        "productions": {
            "total": sum(by_status.values()),
            "published": by_status.get(PublicationStatus.published, 0),
            "draft": by_status.get(PublicationStatus.draft, 0),
            "archived": by_status.get(PublicationStatus.archived, 0),
        },
        "performances": {"upcoming": upcoming_total, "upcoming_public": upcoming_public, "upcoming_draft": draft_perfs},
        "next_performances": [
            {**serialize.performance_public(p), "visibility": p.visibility.value} for p in next_perfs
        ],
        "incomplete_productions": incomplete,
        "recent_activity": [
            {"at": a.created_at.isoformat(), "actor": a.actor_email, "action": a.action, "summary": a.summary,
             "entity_type": a.entity_type, "entity_id": a.entity_id}
            for a in recent
        ],
        "notifications": {"pending": pending_jobs, "failed_7d": failed_jobs, "active_devices": active_devices},
        "articles": {"draft": draft_articles},
        "tasks": tasks,
    }


# ---------------------------------------------------------------- staff


class InviteIn(StrictModel):
    email: EmailStr
    full_name: ReqText = Field(max_length=200)
    role: AdminRole = AdminRole.editor


class UserPatch(StrictModel):
    full_name: ReqText | None = Field(default=None, max_length=200)
    role: AdminRole | None = None


def user_dict(u: AdminUser) -> dict:
    return {
        "id": str(u.id), "email": u.email, "full_name": u.full_name, "role": u.role.value,
        "is_active": u.is_active, "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "created_at": u.created_at.isoformat(), "locked": bool(u.locked_until and u.locked_until > utcnow()),
    }


def invitation_dict(i: AdminInvitation) -> dict:
    now = utcnow()
    state = ("accepted" if i.accepted_at else "revoked" if i.revoked_at else
             "expired" if i.expires_at <= now else "pending")
    return {"id": str(i.id), "email": i.email, "full_name": i.full_name, "role": i.role.value, "state": state,
            "expires_at": i.expires_at.isoformat(), "created_at": i.created_at.isoformat(),
            "invited_by": i.invited_by.full_name if i.invited_by else None}


@router.get("/users", tags=["admin-staff"])
def list_users(db: Session = Depends(get_db), _: AdminUser = Depends(require_admin)):
    users = db.scalars(select(AdminUser).order_by(AdminUser.is_active.desc(), AdminUser.full_name)).all()
    invs = db.scalars(select(AdminInvitation).order_by(AdminInvitation.created_at.desc()).limit(50)).unique().all()
    return {"users": [user_dict(u) for u in users], "invitations": [invitation_dict(i) for i in invs]}


@router.post("/invitations", status_code=201, tags=["admin-staff"])
def invite(body: InviteIn, request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_admin)):
    inv, raw = auth_service.create_invitation(db, email=body.email, full_name=body.full_name, role=body.role,
                                              invited_by=user, ip=client_ip(request))
    db.commit()
    auth_service.send_invitation(inv, raw, user)
    return invitation_dict(inv)


@router.post("/invitations/{invitation_id}/resend", tags=["admin-staff"])
def resend_invitation(invitation_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                      user: AdminUser = Depends(require_admin)):
    old = db.get(AdminInvitation, invitation_id)
    if not old or old.accepted_at:
        raise not_found("Davet bulunamadı veya zaten kabul edilmiş.")
    inv, raw = auth_service.create_invitation(db, email=old.email, full_name=old.full_name, role=old.role,
                                              invited_by=user, ip=client_ip(request))
    db.commit()
    auth_service.send_invitation(inv, raw, user)
    return invitation_dict(inv)


@router.delete("/invitations/{invitation_id}", tags=["admin-staff"])
def revoke_invitation(invitation_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                      user: AdminUser = Depends(require_admin)):
    inv = db.get(AdminInvitation, invitation_id)
    if not inv:
        raise not_found("Davet bulunamadı.")
    if inv.accepted_at:
        raise conflict("already_accepted", "Kabul edilmiş bir davet geri alınamaz; kullanıcının erişimini kapatın.")
    inv.revoked_at = inv.revoked_at or utcnow()
    audit.record(db, user, "admin.invitation_revoked", entity_type="admin_invitation", entity_id=inv.id,
                 summary=f"Davet iptal edildi: {inv.email}", ip=client_ip(request))
    db.commit()
    return invitation_dict(inv)


def _active_admins(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(AdminUser).where(
        AdminUser.role == AdminRole.admin, AdminUser.is_active.is_(True)))


@router.patch("/users/{user_id}", tags=["admin-staff"])
def update_user(user_id: uuid.UUID, body: UserPatch, request: Request, db: Session = Depends(get_db),
                actor: AdminUser = Depends(require_admin)):
    u = db.get(AdminUser, user_id)
    if not u:
        raise not_found("Kullanıcı bulunamadı.")
    if body.role and body.role != u.role and u.role == AdminRole.admin and _active_admins(db) <= 1:
        raise conflict("last_admin", "Sistemde en az bir aktif yönetici kalmalıdır.")
    changes = {}
    if body.full_name:
        changes["full_name"] = body.full_name
        u.full_name = body.full_name
    if body.role:
        changes["role"] = body.role.value
        u.role = body.role
    audit.record(db, actor, "admin.user_updated", entity_type="admin_user", entity_id=u.id,
                 summary=f"Kullanıcı güncellendi: {u.email}", details=changes, ip=client_ip(request))
    db.commit()
    return user_dict(u)


@router.post("/users/{user_id}/deactivate", tags=["admin-staff"])
def deactivate_user(user_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                    actor: AdminUser = Depends(require_admin)):
    u = db.get(AdminUser, user_id)
    if not u:
        raise not_found("Kullanıcı bulunamadı.")
    if u.id == actor.id:
        raise bad_request("self_deactivate", "Kendi erişiminizi kapatamazsınız.")
    if u.role == AdminRole.admin and u.is_active and _active_admins(db) <= 1:
        raise conflict("last_admin", "Sistemde en az bir aktif yönetici kalmalıdır.")
    u.is_active = False
    u.deactivated_at = utcnow()
    auth_service.revoke_all_sessions(db, u.id)
    audit.record(db, actor, "admin.user_deactivated", entity_type="admin_user", entity_id=u.id,
                 summary=f"Erişim kapatıldı: {u.email}", ip=client_ip(request))
    db.commit()
    return user_dict(u)


@router.post("/users/{user_id}/reactivate", tags=["admin-staff"])
def reactivate_user(user_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                    actor: AdminUser = Depends(require_admin)):
    u = db.get(AdminUser, user_id)
    if not u:
        raise not_found("Kullanıcı bulunamadı.")
    u.is_active = True
    u.deactivated_at = None
    u.failed_login_count = 0
    u.locked_until = None
    audit.record(db, actor, "admin.user_reactivated", entity_type="admin_user", entity_id=u.id,
                 summary=f"Erişim yeniden açıldı: {u.email}", ip=client_ip(request))
    db.commit()
    return user_dict(u)


# ---------------------------------------------------------------- notifications


class CategoryIn(StrictModel):
    enabled: bool
    title_template: ReqText = Field(max_length=120)
    body_template: ReqText = Field(max_length=400)


class PolicyIn(StrictModel):
    reminder_lead_minutes: list[Annotated[int, Field(ge=30, le=60 * 24 * 14)]] = Field(max_length=5)
    max_per_device_per_day: int = Field(ge=0, le=20)
    broadcast_cooldown_minutes: int = Field(ge=0, le=60 * 24 * 7)

    @field_validator("reminder_lead_minutes")
    @classmethod
    def _uniq(cls, v: list[int]) -> list[int]:
        return sorted(set(v), reverse=True)


class PreviewIn(StrictModel):
    category: NotificationCategory
    title_template: str | None = Field(default=None, max_length=120)
    body_template: str | None = Field(default=None, max_length=400)
    production_id: uuid.UUID | None = None
    performance_id: uuid.UUID | None = None


CATEGORY_LABELS = {
    NotificationCategory.new_production: "Yeni oyun",
    NotificationCategory.performance_reminder: "Temsil hatırlatması",
    NotificationCategory.performance_cancelled: "Program değişikliği — iptal",
    NotificationCategory.performance_rescheduled: "Program değişikliği — yeni tarih",
}


def job_dict(j: NotificationJob) -> dict:
    return {
        "id": str(j.id), "category": j.category.value, "category_label": CATEGORY_LABELS[j.category],
        "status": j.status.value, "scheduled_for": j.scheduled_for.isoformat(),
        "next_attempt_at": j.next_attempt_at.isoformat(), "attempts": j.attempts, "max_attempts": j.max_attempts,
        "title": j.title, "body": j.body, "data": j.data, "lead_minutes": j.lead_minutes,
        "production_id": str(j.production_id) if j.production_id else None,
        "performance_id": str(j.performance_id) if j.performance_id else None,
        "triggered_by": j.triggered_by, "last_error": j.last_error, "cancel_reason": j.cancel_reason,
        "stats": j.stats or {}, "created_at": j.created_at.isoformat(),
        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
    }


@router.get("/notifications/settings", tags=["admin-notifications"])
def notification_settings(db: Session = Depends(get_db), _: AdminUser = Depends(require_editor)):
    policy = engine.get_policy(db)
    cats = engine.category_settings(db)
    devices = dict(db.execute(select(PushDevice.platform, func.count()).where(PushDevice.is_active.is_(True))
                              .group_by(PushDevice.platform)).all())
    return {
        "categories": [
            {"category": c.value, "label": CATEGORY_LABELS[c], "enabled": cats[c].enabled,
             "title_template": cats[c].title_template, "body_template": cats[c].body_template,
             "placeholders": [{"name": p, "label": templates.PLACEHOLDER_HELP_TR[p]}
                              for p in templates.PLACEHOLDERS[c]]}
            for c in NotificationCategory if c in cats
        ],
        "policy": {"reminder_lead_minutes": policy.reminder_lead_minutes,
                   "max_per_device_per_day": policy.max_per_device_per_day,
                   "broadcast_cooldown_minutes": policy.broadcast_cooldown_minutes},
        "devices": {p.value: devices.get(p, 0) for p in DevicePlatform},
        "provider": get_settings().push_provider,
    }


@router.put("/notifications/categories/{category}", tags=["admin-notifications"])
def update_category(category: NotificationCategory, body: CategoryIn, request: Request,
                    db: Session = Depends(get_db), user: AdminUser = Depends(require_admin)):
    for field, tpl in (("title_template", body.title_template), ("body_template", body.body_template)):
        if err := templates.validate_template(category, tpl):
            raise AppError(422, "validation_error", "Şablonda hata var.",
                           {"fields": [{"field": field, "message": err}]})
    s = db.get(NotificationCategorySetting, category)
    before = {"enabled": s.enabled, "title": s.title_template, "body": s.body_template}
    s.enabled, s.title_template, s.body_template = body.enabled, body.title_template, body.body_template
    s.updated_at, s.updated_by_id = utcnow(), user.id
    if not body.enabled:
        engine.cancel_stale_jobs(db)
    audit.record(db, user, "notifications.category_updated", entity_type="notification_category",
                 entity_id=category.value, summary=f"Bildirim ayarı güncellendi: {CATEGORY_LABELS[category]}",
                 details={"before": before, "after": body.model_dump()}, ip=client_ip(request))
    db.commit()
    return notification_settings(db, user)


@router.put("/notifications/policy", tags=["admin-notifications"])
def update_policy(body: PolicyIn, request: Request, db: Session = Depends(get_db),
                  user: AdminUser = Depends(require_admin)):
    p = engine.get_policy(db)
    before = {"reminder_lead_minutes": p.reminder_lead_minutes, "max_per_device_per_day": p.max_per_device_per_day,
              "broadcast_cooldown_minutes": p.broadcast_cooldown_minutes}
    p.reminder_lead_minutes = body.reminder_lead_minutes
    p.max_per_device_per_day = body.max_per_device_per_day
    p.broadcast_cooldown_minutes = body.broadcast_cooldown_minutes
    p.updated_at, p.updated_by_id = utcnow(), user.id
    engine.cancel_stale_jobs(db)
    engine.plan_reminders(db)
    audit.record(db, user, "notifications.policy_updated", entity_type="notification_policy", entity_id=1,
                 summary="Bildirim kuralları güncellendi", details={"before": before, "after": body.model_dump()},
                 ip=client_ip(request))
    db.commit()
    return notification_settings(db, user)


@router.post("/notifications/preview", tags=["admin-notifications"])
def preview_notification(body: PreviewIn, db: Session = Depends(get_db), _: AdminUser = Depends(require_editor)):
    setting = db.get(NotificationCategorySetting, body.category)
    title_t = body.title_template if body.title_template is not None else setting.title_template
    body_t = body.body_template if body.body_template is not None else setting.body_template
    errors = [e for e in (templates.validate_template(body.category, title_t),
                          templates.validate_template(body.category, body_t)) if e]
    if errors:
        raise AppError(422, "validation_error", errors[0])
    values, source = dict(templates.SAMPLE_VALUES), "sample"
    if body.category == NotificationCategory.new_production and body.production_id:
        p = db.get(Production, body.production_id)
        if p:
            values.update(templates.production_values(p))
            source = "production"
    elif body.performance_id:
        perf = db.get(Performance, body.performance_id)
        if perf:
            values.update({k: v for k, v in templates.performance_values(perf).items() if v})
            source = "performance"
    return {"title": templates.render(title_t, values), "body": templates.render(body_t, values), "source": source}


@router.get("/notifications/jobs", tags=["admin-notifications"])
def list_jobs(
    status: JobStatus | None = None,
    category: NotificationCategory | None = None,
    page: PageNo = 1,
    page_size: PageSize = 50,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_editor),
):
    q = select(NotificationJob)
    if status:
        q = q.where(NotificationJob.status == status)
    if category:
        q = q.where(NotificationJob.category == category)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(NotificationJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return {"items": [job_dict(j) for j in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/notifications/jobs/{job_id}", tags=["admin-notifications"])
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db), _: AdminUser = Depends(require_editor)):
    j = db.get(NotificationJob, job_id)
    if not j:
        raise not_found("Bildirim işi bulunamadı.")
    errors = db.execute(
        select(NotificationDelivery.error_code, func.count())
        .where(NotificationDelivery.job_id == j.id, NotificationDelivery.error_code.is_not(None))
        .group_by(NotificationDelivery.error_code)
    ).all()
    return {**job_dict(j), "error_breakdown": [{"code": c, "count": n} for c, n in errors]}


@router.post("/notifications/jobs/{job_id}/cancel", tags=["admin-notifications"])
def cancel_job(job_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
               user: AdminUser = Depends(require_admin)):
    j = db.get(NotificationJob, job_id)
    if not j:
        raise not_found("Bildirim işi bulunamadı.")
    if j.status != JobStatus.pending:
        raise conflict("not_pending", "Yalnızca bekleyen bildirimler iptal edilebilir.")
    j.status, j.cancel_reason, j.completed_at = JobStatus.cancelled, "admin_cancelled", utcnow()
    audit.record(db, user, "notifications.job_cancelled", entity_type="notification_job", entity_id=j.id,
                 summary=f"Bildirim iptal edildi: {CATEGORY_LABELS[j.category]}", ip=client_ip(request))
    db.commit()
    return job_dict(j)


@router.post("/notifications/jobs/{job_id}/retry", tags=["admin-notifications"],
             summary="Retry a failed job. Devices that already received it are never sent to again.")
def retry_job(job_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
              user: AdminUser = Depends(require_admin)):
    j = db.get(NotificationJob, job_id)
    if not j:
        raise not_found("Bildirim işi bulunamadı.")
    if j.status != JobStatus.failed:
        raise conflict("not_failed", "Yalnızca başarısız bildirimler yeniden denenebilir.")
    j.status, j.attempts, j.next_attempt_at, j.completed_at = JobStatus.pending, 0, utcnow(), None
    audit.record(db, user, "notifications.job_retried", entity_type="notification_job", entity_id=j.id,
                 summary=f"Bildirim yeniden denenecek: {CATEGORY_LABELS[j.category]}", ip=client_ip(request))
    db.commit()
    return job_dict(j)


# ---------------------------------------------------------------- organisation profile


class ValueItem(StrictModel):
    title: ReqText = Field(max_length=100)
    text: ReqText = Field(max_length=1000)


class AboutIn(StrictModel):
    motto: OptText = Field(default=None, max_length=200)
    story_title: OptText = Field(default=None, max_length=200)
    story: OptText = Field(default=None, max_length=10000)
    quote: OptText = Field(default=None, max_length=500)
    quote_author: OptText = Field(default=None, max_length=200)
    values: list[ValueItem] = Field(default_factory=list, max_length=12)
    mission: OptText = Field(default=None, max_length=3000)
    vision: OptText = Field(default=None, max_length=3000)


class OrganizationIn(StrictModel):
    name: ReqText = Field(max_length=200)
    short_name: OptText = Field(default=None, max_length=80)
    address: OptText = Field(default=None, max_length=400)
    phones: list[Annotated[str, Field(pattern=r"^\+?[0-9 ()-]{7,25}$")]] = Field(default_factory=list, max_length=5)
    email: EmailStr | None = None
    website_url: HttpsUrl = None
    instagram_url: HttpsUrl = None
    x_url: HttpsUrl = None
    youtube_url: HttpsUrl = None
    about: AboutIn = Field(default_factory=AboutIn)
    logo_id: uuid.UUID | None = None


def org_dict(o: OrganizationProfile) -> dict:
    return {"name": o.name, "short_name": o.short_name, "address": o.address, "phones": o.phones or [],
            "email": o.email, "website_url": o.website_url, "instagram_url": o.instagram_url, "x_url": o.x_url,
            "youtube_url": o.youtube_url, "about": o.about or {}, "logo": image_dict(o.logo),
            "logo_id": str(o.logo_id) if o.logo_id else None}


@router.get("/organization", tags=["admin-organization"])
def get_org(db: Session = Depends(get_db), _: AdminUser = Depends(require_editor)):
    o = db.get(OrganizationProfile, 1)
    if not o:
        raise not_found("Kurum bilgisi henüz girilmemiş.")
    return org_dict(o)


@router.put("/organization", tags=["admin-organization"])
def put_org(body: OrganizationIn, request: Request, db: Session = Depends(get_db),
            user: AdminUser = Depends(require_admin)):
    if body.logo_id and not db.get(MediaAsset, body.logo_id):
        raise not_found("Logo görseli bulunamadı.")
    o = db.get(OrganizationProfile, 1) or OrganizationProfile(id=1)
    data = body.model_dump()
    for k, v in data.items():
        setattr(o, k, v)
    o.updated_at = utcnow()
    db.add(o)
    audit.record(db, user, "organization.updated", entity_type="organization", entity_id=1,
                 summary="Kurum bilgileri güncellendi", ip=client_ip(request))
    db.commit()
    db.refresh(o)
    return org_dict(o)


# ---------------------------------------------------------------- legal documents


class LegalIn(StrictModel):
    title: ReqText = Field(max_length=200)
    body: ReqText = Field(max_length=100000)
    applies_to: Annotated[str, Field(pattern="^(mobile_app|website|all)$")] = "all"
    review_note: OptText = Field(default=None, max_length=5000)


def legal_dict(d: LegalDocument) -> dict:
    return {"id": str(d.id), "slug": d.slug, "title": d.title, "body": d.body, "applies_to": d.applies_to,
            "status": d.status.value, "review_note": d.review_note, "updated_at": d.updated_at.isoformat(),
            "published_at": d.published_at.isoformat() if d.published_at else None}


@router.get("/legal", tags=["admin-legal"])
def list_legal(db: Session = Depends(get_db), _: AdminUser = Depends(require_admin)):
    return {"items": [legal_dict(d) for d in db.scalars(select(LegalDocument).order_by(LegalDocument.title))]}


@router.put("/legal/{doc_id}", tags=["admin-legal"])
def update_legal(doc_id: uuid.UUID, body: LegalIn, request: Request, db: Session = Depends(get_db),
                 user: AdminUser = Depends(require_admin)):
    d = db.get(LegalDocument, doc_id)
    if not d:
        raise not_found("Belge bulunamadı.")
    for k, v in body.model_dump().items():
        setattr(d, k, v)
    audit.record(db, user, "legal.updated", entity_type="legal_document", entity_id=d.id,
                 summary=f"Yasal metin güncellendi: {d.title}", ip=client_ip(request))
    db.commit()
    return legal_dict(d)


@router.post("/legal/{doc_id}/publish", tags=["admin-legal"])
def publish_legal(doc_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                  user: AdminUser = Depends(require_admin)):
    d = db.get(LegalDocument, doc_id)
    if not d:
        raise not_found("Belge bulunamadı.")
    d.status, d.published_at = Visibility.published, utcnow()
    audit.record(db, user, "legal.published", entity_type="legal_document", entity_id=d.id,
                 summary=f"Yasal metin yayınlandı: {d.title}", ip=client_ip(request))
    db.commit()
    return legal_dict(d)


@router.post("/legal/{doc_id}/unpublish", tags=["admin-legal"])
def unpublish_legal(doc_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                    user: AdminUser = Depends(require_admin)):
    d = db.get(LegalDocument, doc_id)
    if not d:
        raise not_found("Belge bulunamadı.")
    d.status = Visibility.draft
    audit.record(db, user, "legal.unpublished", entity_type="legal_document", entity_id=d.id,
                 summary=f"Yasal metin yayından kaldırıldı: {d.title}", ip=client_ip(request))
    db.commit()
    return legal_dict(d)


# ---------------------------------------------------------------- audit log


@router.get("/audit", tags=["admin-audit"])
def audit_log(
    action: Annotated[str | None, Query(max_length=64)] = None,
    entity_type: Annotated[str | None, Query(max_length=40)] = None,
    page: PageNo = 1,
    page_size: PageSize = 50,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    q = select(AuditLog)
    if action:
        q = q.where(AuditLog.action.startswith(action))
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return {
        "items": [{"id": a.id, "at": a.created_at.isoformat(), "actor": a.actor_email, "action": a.action,
                   "entity_type": a.entity_type, "entity_id": a.entity_id, "summary": a.summary,
                   "details": a.details, "ip": a.ip} for a in rows],
        "total": total, "page": page, "page_size": page_size,
    }
