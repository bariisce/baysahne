"""Notification planning and dispatch.

Guarantees
- A logical event is enqueued at most once (UNIQUE dedupe_key, INSERT ... ON CONFLICT DO NOTHING).
- Each device is attempted at most once per job: a (job_id, device_id) delivery row is committed
  *before* the provider call. If the process dies mid-call, the row stays `queued` and the device
  is not retried, so delivery is at-most-once.
- Jobs are claimed with FOR UPDATE SKIP LOCKED, which makes several workers safe.
- Before sending, every job is re-validated against current data (cancelled, unpublished,
  rescheduled, category disabled, lead time removed). Stale jobs are cancelled, never sent.
- Provider outages are retried with exponential backoff up to max_attempts, and the outcome is recorded.
"""

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.text import utcnow
from app.models import (
    DeliveryStatus,
    JobStatus,
    NotificationCategory,
    NotificationCategorySetting,
    NotificationDelivery,
    NotificationJob,
    NotificationPolicy,
    Performance,
    PerformanceStatus,
    PermissionState,
    Production,
    PublicationStatus,
    PushDevice,
    Visibility,
)
from app.notifications import templates
from app.notifications.providers import BATCH_SIZE, ProviderUnavailable, PushMessage

log = logging.getLogger("baysahne.notifications")

REMINDER_LATE_GRACE = timedelta(minutes=15)  # reminders whose send time passed longer ago are skipped
STUCK_AFTER = timedelta(minutes=15)
RECEIPT_DELAY = timedelta(minutes=15)
FREQUENCY_CAPPED = {NotificationCategory.new_production, NotificationCategory.performance_reminder}


# ---------------------------------------------------------------- settings


def get_policy(db: Session) -> NotificationPolicy:
    policy = db.get(NotificationPolicy, 1)
    if policy is None:  # migration seeds it; recreate defensively
        policy = NotificationPolicy(id=1, reminder_lead_minutes=[1440], max_per_device_per_day=3,
                                    broadcast_cooldown_minutes=60)
        db.add(policy)
        db.flush()
    return policy


def category_settings(db: Session) -> dict[NotificationCategory, NotificationCategorySetting]:
    return {s.category: s for s in db.scalars(select(NotificationCategorySetting))}


def is_enabled(db: Session, category: NotificationCategory) -> bool:
    s = db.get(NotificationCategorySetting, category)
    return bool(s and s.enabled)


# ---------------------------------------------------------------- enqueue


def enqueue(
    db: Session,
    *,
    category: NotificationCategory,
    dedupe_key: str,
    scheduled_for: datetime,
    data: dict,
    production_id: uuid.UUID | None = None,
    performance_id: uuid.UUID | None = None,
    lead_minutes: int | None = None,
    triggered_by: str = "system",
    created_by_id: uuid.UUID | None = None,
) -> NotificationJob | None:
    """Insert a job unless one with the same dedupe_key exists. Returns the new job or None."""
    stmt = (
        pg_insert(NotificationJob)
        .values(
            id=uuid.uuid4(),
            category=category,
            dedupe_key=dedupe_key,
            status=JobStatus.pending,
            scheduled_for=scheduled_for,
            next_attempt_at=scheduled_for,
            attempts=0,
            max_attempts=5,
            data=data,
            production_id=production_id,
            performance_id=performance_id,
            lead_minutes=lead_minutes,
            triggered_by=triggered_by,
            created_by_id=created_by_id,
            stats={},
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
        .returning(NotificationJob.id)
    )
    new_id = db.execute(stmt).scalar()
    return db.get(NotificationJob, new_id) if new_id else None


def _perf_data(perf: Performance) -> dict:
    return {
        "type": "performance",
        "production_slug": perf.production.slug,
        "performance_id": str(perf.id),
        "starts_at": perf.starts_at.isoformat(),
        "reschedule_count": perf.reschedule_count,
    }


def on_production_published(db: Session, production: Production, actor_id=None) -> NotificationJob | None:
    if not is_enabled(db, NotificationCategory.new_production):
        return None
    return enqueue(
        db,
        category=NotificationCategory.new_production,
        dedupe_key=f"new_production:{production.id}",
        scheduled_for=utcnow(),
        data={"type": "production", "production_slug": production.slug},
        production_id=production.id,
        triggered_by="admin",
        created_by_id=actor_id,
    )


def _announced_and_upcoming(perf: Performance, now: datetime, starts_at: datetime) -> bool:
    return (
        perf.first_published_at is not None
        and perf.production.status == PublicationStatus.published
        and starts_at > now
    )


def on_performance_cancelled(db: Session, perf: Performance, actor_id=None) -> NotificationJob | None:
    cancel_pending_for_performance(db, perf.id, "performance_cancelled",
                                   categories=[NotificationCategory.performance_reminder,
                                               NotificationCategory.performance_rescheduled])
    if not is_enabled(db, NotificationCategory.performance_cancelled):
        return None
    if not _announced_and_upcoming(perf, utcnow(), perf.starts_at):
        return None
    return enqueue(
        db,
        category=NotificationCategory.performance_cancelled,
        dedupe_key=f"performance_cancelled:{perf.id}",
        scheduled_for=utcnow(),
        data=_perf_data(perf),
        production_id=perf.production_id,
        performance_id=perf.id,
        triggered_by="admin",
        created_by_id=actor_id,
    )


def on_performance_rescheduled(db: Session, perf: Performance, actor_id=None) -> NotificationJob | None:
    # Old reminders carry the old start time in their dedupe key; the planner cancels them and plans new ones.
    cancel_stale_jobs(db, utcnow())
    if not is_enabled(db, NotificationCategory.performance_rescheduled):
        return None
    if perf.visibility != Visibility.published or perf.status != PerformanceStatus.scheduled:
        return None
    if not _announced_and_upcoming(perf, utcnow(), perf.starts_at):
        return None
    return enqueue(
        db,
        category=NotificationCategory.performance_rescheduled,
        dedupe_key=f"performance_rescheduled:{perf.id}:{perf.reschedule_count}",
        scheduled_for=utcnow(),
        data=_perf_data(perf),
        production_id=perf.production_id,
        performance_id=perf.id,
        triggered_by="admin",
        created_by_id=actor_id,
    )


def cancel_pending_for_performance(db: Session, performance_id, reason: str, categories=None) -> int:
    q = update(NotificationJob).where(
        NotificationJob.performance_id == performance_id, NotificationJob.status == JobStatus.pending
    )
    if categories:
        q = q.where(NotificationJob.category.in_(categories))
    res = db.execute(q.values(status=JobStatus.cancelled, cancel_reason=reason, completed_at=utcnow()))
    return res.rowcount or 0


# ---------------------------------------------------------------- planning


def reminder_key(perf: Performance, lead: int) -> str:
    return f"performance_reminder:{perf.id}:{lead}:{int(perf.starts_at.timestamp())}"


def plan_reminders(db: Session, now: datetime | None = None) -> int:
    """Create reminder jobs for every eligible upcoming performance and configured lead time."""
    now = now or utcnow()
    if not is_enabled(db, NotificationCategory.performance_reminder):
        return 0
    leads = sorted(set(get_policy(db).reminder_lead_minutes or []))
    if not leads:
        return 0
    perfs = db.scalars(
        select(Performance)
        .join(Production, Production.id == Performance.production_id)
        .where(
            Performance.visibility == Visibility.published,
            Performance.status == PerformanceStatus.scheduled,
            Production.status == PublicationStatus.published,
            Performance.starts_at > now,
        )
    ).unique()
    created = 0
    for perf in perfs:
        for lead in leads:
            send_at = perf.starts_at - timedelta(minutes=lead)
            if send_at < now - REMINDER_LATE_GRACE:
                continue
            job = enqueue(
                db,
                category=NotificationCategory.performance_reminder,
                dedupe_key=reminder_key(perf, lead),
                scheduled_for=max(send_at, now),
                data=_perf_data(perf),
                production_id=perf.production_id,
                performance_id=perf.id,
                lead_minutes=lead,
            )
            created += 1 if job else 0
    return created


def validate_job(db: Session, job: NotificationJob, now: datetime) -> str | None:
    """Return a cancellation reason if the job must not be sent, else None."""
    if not is_enabled(db, job.category):
        return "category_disabled"
    if job.category == NotificationCategory.new_production:
        p = db.get(Production, job.production_id) if job.production_id else None
        if not p or p.status != PublicationStatus.published:
            return "production_not_published"
        return None

    perf = db.get(Performance, job.performance_id) if job.performance_id else None
    if not perf:
        return "performance_deleted"
    if perf.production.status != PublicationStatus.published:
        return "production_not_published"
    if perf.starts_at <= now:
        return "performance_started"

    if job.category == NotificationCategory.performance_reminder:
        if perf.status != PerformanceStatus.scheduled:
            return "performance_cancelled"
        if perf.visibility != Visibility.published:
            return "performance_unpublished"
        if job.data.get("starts_at") != perf.starts_at.isoformat():
            return "performance_rescheduled"
        if job.lead_minutes not in (get_policy(db).reminder_lead_minutes or []):
            return "lead_time_removed"
    elif job.category == NotificationCategory.performance_cancelled:
        if perf.status != PerformanceStatus.cancelled:
            return "performance_restored"
    elif job.category == NotificationCategory.performance_rescheduled:
        if perf.status != PerformanceStatus.scheduled or perf.visibility != Visibility.published:
            return "performance_not_active"
        if job.data.get("reschedule_count") != perf.reschedule_count:
            return "superseded_by_newer_reschedule"
    return None


def cancel_stale_jobs(db: Session, now: datetime | None = None) -> int:
    now = now or utcnow()
    n = 0
    for job in db.scalars(select(NotificationJob).where(NotificationJob.status == JobStatus.pending)):
        reason = validate_job(db, job, now)
        if reason:
            job.status = JobStatus.cancelled
            job.cancel_reason = reason
            job.completed_at = now
            n += 1
    return n


# ---------------------------------------------------------------- dispatch


def recover_stuck(db: Session, now: datetime) -> int:
    stuck = db.scalars(
        select(NotificationJob).where(
            NotificationJob.status == JobStatus.processing, NotificationJob.locked_at < now - STUCK_AFTER
        )
    ).all()
    for job in stuck:
        # Devices whose provider call was interrupted are NOT retried (at-most-once).
        db.execute(
            update(NotificationDelivery)
            .where(NotificationDelivery.job_id == job.id, NotificationDelivery.status == DeliveryStatus.queued)
            .values(status=DeliveryStatus.error, error_code="interrupted",
                    error_message="Worker stopped during the provider call; not retried to avoid duplicates.")
        )
        job.status = JobStatus.pending
        job.locked_at = None
        job.next_attempt_at = now
    return len(stuck)


def _claim(db: Session, now: datetime, limit: int) -> list[uuid.UUID]:
    ids = db.scalars(
        select(NotificationJob.id)
        .where(NotificationJob.status == JobStatus.pending, NotificationJob.next_attempt_at <= now)
        .order_by(NotificationJob.next_attempt_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    if ids:
        db.execute(
            update(NotificationJob)
            .where(NotificationJob.id.in_(ids))
            .values(status=JobStatus.processing, locked_at=now, attempts=NotificationJob.attempts + 1)
        )
    db.commit()
    return list(ids)


def _render(db: Session, job: NotificationJob) -> tuple[str, str]:
    setting = db.get(NotificationCategorySetting, job.category)
    if job.category == NotificationCategory.new_production:
        values = templates.production_values(db.get(Production, job.production_id))
    else:
        values = templates.performance_values(db.get(Performance, job.performance_id))
    return templates.render(setting.title_template, values), templates.render(setting.body_template, values)


def _finish(job: NotificationJob, db: Session, now: datetime) -> None:
    rows = db.execute(
        select(NotificationDelivery.status, func.count())
        .where(NotificationDelivery.job_id == job.id)
        .group_by(NotificationDelivery.status)
    ).all()
    counts = {status.value: n for status, n in rows}
    job.stats = {
        "targeted": sum(counts.values()),
        "ok": counts.get("ok", 0),
        "error": counts.get("error", 0),
        "rate_limited": counts.get("rate_limited", 0),
    }
    job.status = JobStatus.sent
    job.completed_at = now
    job.locked_at = None


def _deactivate_token(db: Session, device_id, reason: str, now: datetime) -> None:
    db.execute(
        update(PushDevice)
        .where(PushDevice.id == device_id)
        .values(is_active=False, deactivated_at=now, deactivation_reason=reason)
    )


def dispatch_job(db: Session, job_id: uuid.UUID, provider, now: datetime) -> None:
    job = db.get(NotificationJob, job_id)
    reason = validate_job(db, job, now)
    if reason:
        job.status, job.cancel_reason, job.completed_at, job.locked_at = JobStatus.cancelled, reason, now, None
        db.commit()
        return

    policy = get_policy(db)
    if job.category == NotificationCategory.new_production and policy.broadcast_cooldown_minutes > 0:
        last = db.scalar(
            select(func.max(NotificationJob.completed_at)).where(
                NotificationJob.category == NotificationCategory.new_production,
                NotificationJob.status == JobStatus.sent,
                NotificationJob.id != job.id,
            )
        )
        if last and last > now - timedelta(minutes=policy.broadcast_cooldown_minutes):
            job.status = JobStatus.pending
            job.attempts -= 1
            job.locked_at = None
            job.next_attempt_at = last + timedelta(minutes=policy.broadcast_cooldown_minutes)
            db.commit()
            return

    job.title, job.body = _render(db, job)
    db.commit()

    capped = job.category in FREQUENCY_CAPPED
    while True:
        already = select(NotificationDelivery.device_id).where(NotificationDelivery.job_id == job.id)
        devices = db.execute(
            select(PushDevice.id, PushDevice.push_token)
            .where(
                PushDevice.is_active.is_(True),
                PushDevice.permission == PermissionState.granted,
                PushDevice.push_token.is_not(None),
                PushDevice.id.not_in(already),
            )
            .order_by(PushDevice.id)
            .limit(BATCH_SIZE)
        ).all()
        if not devices:
            break

        limited: set = set()
        if capped and policy.max_per_device_per_day > 0:
            counts = dict(
                db.execute(
                    select(NotificationDelivery.device_id, func.count())
                    .where(
                        NotificationDelivery.device_id.in_([d.id for d in devices]),
                        NotificationDelivery.status == DeliveryStatus.ok,
                        NotificationDelivery.created_at > now - timedelta(days=1),
                    )
                    .group_by(NotificationDelivery.device_id)
                ).all()
            )
            limited = {d.id for d in devices if counts.get(d.id, 0) >= policy.max_per_device_per_day}

        sendable = [d for d in devices if d.id not in limited]
        rows = [{"job_id": job.id, "device_id": d.id, "status": DeliveryStatus.rate_limited} for d in devices
                if d.id in limited]
        rows += [{"job_id": job.id, "device_id": d.id, "status": DeliveryStatus.queued} for d in sendable]
        db.execute(pg_insert(NotificationDelivery).values(rows).on_conflict_do_nothing())
        db.commit()  # reservation is durable before the provider is contacted
        if not sendable:
            continue

        messages = [PushMessage(to=d.push_token, title=job.title, body=job.body, data=job.data) for d in sendable]
        try:
            tickets = provider.send(messages)
        except ProviderUnavailable as e:
            # Nothing in this request was accepted: release the reservations so a retry can resend.
            db.execute(
                delete(NotificationDelivery).where(
                    NotificationDelivery.job_id == job.id,
                    NotificationDelivery.status == DeliveryStatus.queued,
                    NotificationDelivery.device_id.in_([d.id for d in sendable]),
                )
            )
            job.last_error = f"Sağlayıcı hatası: {e}"[:1000]
            job.locked_at = None
            if job.attempts >= job.max_attempts:
                job.status = JobStatus.failed
                job.completed_at = now
            else:
                job.status = JobStatus.pending
                job.next_attempt_at = now + timedelta(minutes=2 ** job.attempts)
            db.commit()
            log.warning("push provider unavailable job=%s attempt=%s: %s", job.id, job.attempts, e)
            return

        for d, t in zip(sendable, tickets, strict=True):
            values = {"status": DeliveryStatus.ok if t.ok else DeliveryStatus.error,
                      "provider_ticket_id": t.ticket_id, "error_code": t.error_code,
                      "error_message": t.error_message}
            db.execute(
                update(NotificationDelivery)
                .where(and_(NotificationDelivery.job_id == job.id, NotificationDelivery.device_id == d.id))
                .values(**values)
            )
            if not t.ok and t.error_code == "DeviceNotRegistered":
                _deactivate_token(db, d.id, "device_not_registered", now)
        db.commit()

    _finish(job, db, now)
    db.commit()
    log.info("job %s (%s) sent: %s", job.id, job.category.value, job.stats)


def dispatch_due(db: Session, provider, now: datetime | None = None, limit: int = 10) -> int:
    now = now or utcnow()
    count = 0
    for job_id in _claim(db, now, limit):
        try:
            dispatch_job(db, job_id, provider, now)
        except Exception as e:  # unexpected bug: record it, release the job for a bounded retry
            db.rollback()
            log.exception("dispatch failed for job %s", job_id)
            job = db.get(NotificationJob, job_id)
            job.last_error = f"İç hata: {e.__class__.__name__}"
            job.locked_at = None
            if job.attempts >= job.max_attempts:
                job.status, job.completed_at = JobStatus.failed, now
            else:
                job.status, job.next_attempt_at = JobStatus.pending, now + timedelta(minutes=2 ** job.attempts)
            db.commit()
        count += 1
    return count


def check_receipts(db: Session, provider, now: datetime | None = None, limit: int = 1000) -> int:
    now = now or utcnow()
    rows = db.execute(
        select(NotificationDelivery.id, NotificationDelivery.device_id, NotificationDelivery.provider_ticket_id)
        .where(
            NotificationDelivery.status == DeliveryStatus.ok,
            NotificationDelivery.provider_ticket_id.is_not(None),
            NotificationDelivery.receipt_checked_at.is_(None),
            NotificationDelivery.created_at < now - RECEIPT_DELAY,
        )
        .limit(limit)
    ).all()
    checked = 0
    for i in range(0, len(rows), 300):
        chunk = rows[i:i + 300]
        try:
            receipts = provider.get_receipts([r.provider_ticket_id for r in chunk])
        except ProviderUnavailable as e:
            log.warning("receipt check failed: %s", e)
            break
        for r in chunk:
            rec = receipts.get(r.provider_ticket_id)
            status = rec.get("status", "unknown") if rec else "unknown"
            code = (rec or {}).get("details", {}).get("error") if status == "error" else None
            db.execute(
                update(NotificationDelivery).where(NotificationDelivery.id == r.id).values(
                    receipt_status=status if not code else f"error:{code}"[:32], receipt_checked_at=now)
            )
            if code == "DeviceNotRegistered":
                _deactivate_token(db, r.device_id, "device_not_registered", now)
            checked += 1
        db.commit()
    return checked


def run_once(db: Session, provider, now: datetime | None = None) -> dict:
    now = now or utcnow()
    recovered = recover_stuck(db, now)
    cancelled = cancel_stale_jobs(db, now)
    planned = plan_reminders(db, now)
    db.commit()
    dispatched = dispatch_due(db, provider, now)
    receipts = check_receipts(db, provider, now)
    return {"recovered": recovered, "cancelled": cancelled, "planned": planned, "dispatched": dispatched,
            "receipts": receipts}
