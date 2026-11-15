import re
import unicodedata
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

_TR_MAP = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "İ": "i", "ö": "o", "ş": "s", "ü": "u",
                         "Ç": "c", "Ğ": "g", "Ö": "o", "Ş": "s", "Ü": "u", "&": " ve "})

MONTHS_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül",
             "Ekim", "Kasım", "Aralık"]
WEEKDAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

DEFAULT_TZ = "Europe/Istanbul"


def slugify(value: str) -> str:
    value = value.translate(_TR_MAP)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:150] or "icerik"


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_local(dt: datetime, tz: str | None = None) -> datetime:
    return dt.astimezone(ZoneInfo(tz or DEFAULT_TZ))


def format_date_tr(dt: datetime, tz: str | None = None) -> str:
    d = to_local(dt, tz)
    return f"{d.day} {MONTHS_TR[d.month - 1]}"


def format_weekday_tr(dt: datetime, tz: str | None = None) -> str:
    return WEEKDAYS_TR[to_local(dt, tz).weekday()]


def format_time_tr(dt: datetime, tz: str | None = None) -> str:
    return to_local(dt, tz).strftime("%H:%M")


def clean_text(value: str | None) -> str | None:
    """Trim, normalise line endings, drop control characters. Returns None for blank values."""
    if value is None:
        return None
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = "".join(ch for ch in value if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    value = value.strip()
    return value or None
