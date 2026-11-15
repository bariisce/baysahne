"""Safe rendering of admin-editable Turkish notification templates.

Only plain `{name}` placeholders from a fixed allow-list are accepted. Attribute/index access such as
`{title.__class__}` is rejected at save time, so admin input can never reach Python internals.
"""

from string import Formatter

from app.core.text import format_date_tr, format_time_tr, format_weekday_tr
from app.models import NotificationCategory, Performance, Production

PLACEHOLDERS: dict[NotificationCategory, tuple[str, ...]] = {
    NotificationCategory.new_production: ("title", "genre", "author"),
    NotificationCategory.performance_reminder: ("title", "date", "weekday", "time", "venue"),
    NotificationCategory.performance_cancelled: ("title", "date", "weekday", "time", "venue"),
    NotificationCategory.performance_rescheduled: (
        "title", "date", "weekday", "time", "venue", "old_date", "old_time"),
}

PLACEHOLDER_HELP_TR = {
    "title": "Oyun adı",
    "genre": "Tür",
    "author": "Yazar",
    "date": "Tarih (ör. 18 Ekim)",
    "weekday": "Gün (ör. Pazar)",
    "time": "Saat (ör. 20:30)",
    "venue": "Salon adı",
    "old_date": "Eski tarih",
    "old_time": "Eski saat",
}


def validate_template(category: NotificationCategory, template: str) -> str | None:
    allowed = set(PLACEHOLDERS[category])
    try:
        parsed = list(Formatter().parse(template))
    except ValueError:
        return "Şablonda eşleşmeyen süslü parantez var."
    for _, field, spec, conv in parsed:
        if field is None:
            continue
        if field not in allowed or spec or conv:
            return f"Geçersiz alan: {{{field}}}. Kullanılabilir alanlar: " + ", ".join(
                "{" + p + "}" for p in PLACEHOLDERS[category])
    return None


def render(template: str, values: dict[str, str]) -> str:
    return template.format_map({k: (v or "") for k, v in values.items()}).strip()


def production_values(p: Production) -> dict[str, str]:
    author = next((c.name for c in p.credits if c.role.value == "author"), "")
    return {"title": p.title, "genre": ", ".join(p.genres or []), "author": author}


def performance_values(perf: Performance) -> dict[str, str]:
    tz = perf.venue.timezone
    values = {
        "title": perf.production.title,
        "date": format_date_tr(perf.starts_at, tz),
        "weekday": format_weekday_tr(perf.starts_at, tz),
        "time": format_time_tr(perf.starts_at, tz),
        "venue": perf.venue.name,
        "old_date": "",
        "old_time": "",
    }
    if perf.rescheduled_from:
        values["old_date"] = format_date_tr(perf.rescheduled_from, tz)
        values["old_time"] = format_time_tr(perf.rescheduled_from, tz)
    return values


SAMPLE_VALUES = {
    "title": "Örnek Oyun",
    "genre": "Dram",
    "author": "Örnek Yazar",
    "date": "18 Ekim",
    "weekday": "Pazar",
    "time": "20:30",
    "venue": "Örnek Salon",
    "old_date": "11 Ekim",
    "old_time": "20:00",
}
