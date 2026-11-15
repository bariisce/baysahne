"""Storage abstraction. Database rows store keys; URLs are derived at response time by the active backend,
so switching from local disk to S3/CDN needs no data migration beyond copying objects."""

import re
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import get_settings

# Origin ("http://host:port") of the request being served. In development local media URLs are built from
# it: a phone on the LAN and the admin on localhost each get URLs they can reach, and a changed IP address
# needs no reconfiguration. It deliberately wins over PUBLIC_API_BASE_URL there, because a fixed address
# left in a start command or a shell goes stale the moment the computer joins another network.
_request_origin: ContextVar[str | None] = ContextVar("request_origin", default=None)
_HOST = re.compile(r"^[A-Za-z0-9.\-]+(:\d{1,5})?$|^\[[0-9A-Fa-f:.]+\](:\d{1,5})?$")
_FALLBACK_ORIGIN = "http://localhost:8100"  # outside a request (CLI, worker)


class RequestOrigin:
    """ASGI middleware that records the request's origin for media URLs (development only).

    X-Forwarded-Host wins over Host: the admin panel proxies /api and /media through Next.js, which
    forwards with Host set to the backend, so images resolve to the admin's own origin. Trusting the
    header is acceptable only because this middleware is never installed outside development.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        host = headers.get("x-forwarded-host") or headers.get("host", "")
        proto = headers.get("x-forwarded-proto", scope["scheme"])
        valid = _HOST.match(host) and proto in ("http", "https")
        token = _request_origin.set(f"{proto}://{host}" if valid else None)
        try:
            await self.app(scope, receive, send)
        finally:
            _request_origin.reset(token)


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
    def url(self, key: str) -> str: ...


class LocalStorage:
    """Files under MEDIA_LOCAL_ROOT, served by the API at /media/<key>. Development / single-host only."""

    def __init__(self, root: Path, public_base: str):
        self.root = root
        self.public_base = public_base.rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("invalid storage key")
        return p

    def put(self, key: str, data: bytes, content_type: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(p)

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def url(self, key: str) -> str:
        # The request origin only exists where RequestOrigin is installed (development); deployed APIs
        # always use their configured public address.
        base = _request_origin.get() or self.public_base or _FALLBACK_ORIGIN
        return f"{base}/media/{key}"


class S3Storage:
    """S3-compatible object storage (AWS S3, Cloudflare R2, MinIO, ...). Objects are immutable
    (keys contain a random UUID), so they are uploaded with a long Cache-Control."""

    def __init__(self) -> None:
        import boto3  # optional dependency: pip install ".[s3]"

        s = get_settings()
        self.bucket = s.s3_bucket
        self.public_base = s.s3_public_base_url.rstrip("/")
        self.client = boto3.client(
            "s3",
            region_name=s.s3_region or None,
            endpoint_url=s.s3_endpoint_url or None,
            aws_access_key_id=s.s3_access_key_id or None,
            aws_secret_access_key=s.s3_secret_access_key or None,
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def url(self, key: str) -> str:
        return f"{self.public_base}/{key}"


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    if s.media_storage == "s3":
        return S3Storage()
    return LocalStorage(s.media_root_path, s.public_api_base_url)
