"""Default notification policy and Turkish templates (identical to the values seeded by the initial migration)."""

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import NotificationCategorySetting, NotificationPolicy

DEFAULT_TEMPLATES = {
    "new_production": ("Yeni oyun: {title}", "{title} Bay Sahne repertuvarına eklendi. Ayrıntılar için dokunun."),
    "performance_reminder": ("Hatırlatma: {title}", "{date} {weekday}, saat {time} · {venue}"),
    "performance_cancelled": ("Program değişikliği: {title}", "{date} saat {time} temsili iptal edildi."),
    "performance_rescheduled": (
        "Yeni tarih: {title}",
        "{old_date} saat {old_time} temsili {date} {weekday}, saat {time} tarihine alındı.",
    ),
}


def ensure_defaults(db: Session) -> None:
    """Insert missing rows only; never overwrites staff edits."""
    db.execute(
        pg_insert(NotificationPolicy)
        .values(id=1, reminder_lead_minutes=[1440], max_per_device_per_day=3, broadcast_cooldown_minutes=60)
        .on_conflict_do_nothing()
    )
    for category, (title, body) in DEFAULT_TEMPLATES.items():
        db.execute(
            pg_insert(NotificationCategorySetting)
            .values(category=category, enabled=True, title_template=title, body_template=body)
            .on_conflict_do_nothing()
        )
