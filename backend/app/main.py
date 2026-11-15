import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import db
from app.api import legal_pages
from app.api.admin import auth as admin_auth
from app.api.admin import media_articles, productions, schedule, system
from app.api.public import routes as public_routes
from app.config import get_settings
from app.core import errors
from app.storage import RequestOrigin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("baysahne")


class SecurityHeaders:
    """Adds security and caching headers.

    Pure ASGI rather than BaseHTTPMiddleware: no extra task and stream per request, and requests
    cancelled by client disconnects or shutdown are not wrapped in middleware tracebacks.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope["path"]
        hsts = get_settings().cookie_secure

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
                headers.setdefault("X-Frame-Options", "DENY")
                if path.startswith("/api/v1/admin"):
                    headers["Cache-Control"] = "no-store"
                elif path.startswith("/api/v1/") and message["status"] < 400:
                    # Public content: short shared caching keeps the app snappy without serving stale schedules.
                    headers.setdefault("Cache-Control", "public, max-age=30")
                if hsts:
                    headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
            await send(message)

        await self.app(scope, receive, send_with_headers)


class CachedStatic(StaticFiles):
    """Media keys contain random UUIDs and are never overwritten, so they can be cached forever."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The API still starts without its database (static media and the health check keep working, and
    # requests recover by themselves once it is back), but say so once, loudly, with the remedy.
    if not db.check_connection():
        log.error("DATABASE UNAVAILABLE - every content request will answer 503 until it is back. %s",
                  db.unavailable_hint())
    s = get_settings()
    if s.app_env == "development" and s.public_api_base_url:
        log.warning("PUBLIC_API_BASE_URL=%s is not needed in development and is ignored for requests: media "
                    "URLs follow the address each request came in on. Drop it from the start command.",
                    s.public_api_base_url)
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        lifespan=lifespan,
        title="Bay Sahne API",
        version="1.0.0",
        description="Public content API for the Bay Sahne mobile app and the authenticated admin API.",
        docs_url="/docs" if s.app_env != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if s.app_env != "production" else None,
    )
    errors.install(app)
    app.add_middleware(SecurityHeaders)
    if s.is_dev:
        # Media URLs follow the address each request came in on, so nothing breaks when the computer's
        # IP changes. Never outside development: the middleware trusts the Host / X-Forwarded-Host headers.
        app.add_middleware(RequestOrigin)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Requested-With"],
    )
    for r in (public_routes.router, admin_auth.router, productions.router, schedule.router,
              media_articles.router, system.router, legal_pages.router):
        app.include_router(r)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"status": "ok"}

    if s.media_storage == "local":
        s.media_root_path.mkdir(parents=True, exist_ok=True)
        app.mount("/media", CachedStatic(directory=s.media_root_path), name="media")
    return app


app = create_app()
