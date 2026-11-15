import re
from typing import Annotated
from urllib.parse import urlparse

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.core.text import clean_text


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict | list | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _clean(v: str | None) -> str | None:
    return clean_text(v)


def _required(v: str) -> str:
    v2 = clean_text(v)
    if not v2:
        raise ValueError("Bu alan zorunludur.")
    return v2


def _https_url(v: str | None) -> str | None:
    v = clean_text(v)
    if v is None:
        return None
    u = urlparse(v)
    if u.scheme != "https" or not u.netloc or " " in v:
        raise ValueError("Bağlantı https:// ile başlayan geçerli bir adres olmalıdır.")
    return v


def _slug(v: str | None) -> str | None:
    v = clean_text(v)
    if v is None:
        return None
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", v) or len(v) > 150:
        raise ValueError("Kısa ad yalnızca küçük harf, rakam ve tire içerebilir.")
    return v


OptText = Annotated[str | None, AfterValidator(_clean)]
ReqText = Annotated[str, AfterValidator(_required)]
HttpsUrl = Annotated[str | None, AfterValidator(_https_url)]
Slug = Annotated[str | None, AfterValidator(_slug)]

PageNo = Annotated[int, Field(ge=1, le=10_000)]
PageSize = Annotated[int, Field(ge=1, le=100)]


YOUTUBE_RE = re.compile(
    r"^https://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


def youtube_id(url: str) -> str | None:
    m = YOUTUBE_RE.match(url)
    return m.group(1) if m else None
