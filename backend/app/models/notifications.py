"""Push devices and the persistent notification job queue.

Idempotency layers:
  1. notification_jobs.dedupe_key is UNIQUE → the same logical event can only be enqueued once.
  2. notification_deliveries (job_id, device_id) is UNIQUE → a device is attempted at most once per job,
     even if the worker crashes mid-batch and the job is retried.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin
from app.models._types import str_enum, uuid_pk


class DevicePlatform(enum.StrEnum):
    ios = "ios"
    android = "android"


class PermissionState(enum.StrEnum):
    granted = "granted"
    denied = "denied"
    undetermined = "undetermined"


class NotificationCategory(enum.StrEnum):
    new_production = "new_production"
    performance_reminder = "performance_reminder"
    performance_cancelled = "performance_cancelled"
    performance_rescheduled = "performance_rescheduled"


class JobStatus(enum.StrEnum):
    pending = "pending"
    processing = "processing"
    sent = "sent"
    failed = "failed"
    cancelled = "cancelled"
    skipped = "skipped"


class DeliveryStatus(enum.StrEnum):
    queued = "queued"  # row reserved; provider call in progress or interrupted
    ok = "ok"  # accepted by the provider (ticket issued)
    error = "error"
    rate_limited = "rate_limited"  # skipped by the per-device frequency cap


class PushDevice(TimestampMixin, Base):
    """One app installation. No personal data: a random installation id, the push token and platform."""

    __tablename__ = "push_devices"
    __table_args__ = (Index("ix_push_devices_active", "is_active"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    installation_id: Mapped[str] = mapped_column(String(64), unique=True)
    push_token: Mapped[str | None] = mapped_column(String(255), unique=True)
    platform: Mapped[DevicePlatform] = mapped_column(str_enum(DevicePlatform, "device_platform"))
    app_version: Mapped[str | None] = mapped_column(String(40))
    locale: Mapped[str | None] = mapped_column(String(20))
    permission: Mapped[PermissionState] = mapped_column(
        str_enum(PermissionState, "permission_state"), default=PermissionState.undetermined
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivation_reason: Mapped[str | None] = mapped_column(String(64))


class NotificationCategorySetting(Base):
    __tablename__ = "notification_category_settings"

    category: Mapped[NotificationCategory] = mapped_column(
        str_enum(NotificationCategory, "notification_category"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    title_template: Mapped[str] = mapped_column(String(120))
    body_template: Mapped[str] = mapped_column(String(400))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))


class NotificationPolicy(Base):
    """Singleton (id=1): reminder lead times and frequency limits."""

    __tablename__ = "notification_policy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    reminder_lead_minutes: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=lambda: [1440])
    max_per_device_per_day: Mapped[int] = mapped_column(Integer, default=3)
    broadcast_cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))


class NotificationJob(TimestampMixin, Base):
    __tablename__ = "notification_jobs"
    __table_args__ = (Index("ix_notification_jobs_due", "status", "next_attempt_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    category: Mapped[NotificationCategory] = mapped_column(
        str_enum(NotificationCategory, "job_category"), index=True
    )
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[JobStatus] = mapped_column(str_enum(JobStatus, "job_status"), default=JobStatus.pending)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    # Rendered at dispatch time from the category template so later template edits apply.
    title: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(String(500))
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    production_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("productions.id", ondelete="SET NULL"), index=True
    )
    performance_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("performances.id", ondelete="SET NULL"), index=True
    )
    lead_minutes: Mapped[int | None] = mapped_column(Integer)
    triggered_by: Mapped[str] = mapped_column(String(16), default="system")  # system | admin
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    cancel_reason: Mapped[str | None] = mapped_column(String(120))
    # {"targeted": n, "ok": n, "error": n, "rate_limited": n}
    stats: Mapped[dict] = mapped_column(JSONB, default=dict)

    deliveries: Mapped[list["NotificationDelivery"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", lazy="raise"
    )


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("job_id", "device_id"),
        Index("ix_notification_deliveries_device_created", "device_id", "created_at"),
        Index("ix_notification_deliveries_receipt", "status", "receipt_checked_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notification_jobs.id", ondelete="CASCADE"))
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("push_devices.id", ondelete="CASCADE"))
    status: Mapped[DeliveryStatus] = mapped_column(str_enum(DeliveryStatus, "delivery_status"))
    provider_ticket_id: Mapped[str | None] = mapped_column(String(100))
    receipt_status: Mapped[str | None] = mapped_column(String(32))
    receipt_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[NotificationJob] = relationship(back_populates="deliveries")
