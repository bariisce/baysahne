from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import AppError, forbidden
from app.db import get_db
from app.models import AdminRole, AdminSession, AdminUser
from app.services import auth as auth_service

CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "baysahne-admin"
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def csrf_protect(request: Request) -> None:
    """Defence in depth on top of the SameSite=Strict cookie: unsafe admin requests must carry a custom
    header (which cross-site forms cannot set) and, when present, an allowed Origin."""
    if request.method not in UNSAFE:
        return
    if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise AppError(403, "csrf_failed", "İstek doğrulanamadı. Sayfayı yenileyip tekrar deneyin.")
    origin = request.headers.get("origin")
    if origin:
        s = get_settings()
        allowed = set(s.cors_origins) | {s.admin_base_url.rstrip("/")}
        if origin.rstrip("/") not in allowed:
            raise AppError(403, "csrf_failed", "İstek doğrulanamadı. Sayfayı yenileyip tekrar deneyin.")


def current_session(request: Request, db: Session = Depends(get_db)) -> AdminSession:
    token = request.cookies.get(get_settings().session_cookie_name)
    sess = auth_service.resolve_session(db, token) if token else None
    if not sess:
        raise AppError(401, "unauthorized", "Oturumunuz sona erdi. Lütfen tekrar giriş yapın.")
    return sess


def current_user(
    request: Request, sess: AdminSession = Depends(current_session), _: None = Depends(csrf_protect)
) -> AdminUser:
    request.state.user = sess.user
    return sess.user


def require_role(*roles: AdminRole) -> Callable[[AdminUser], AdminUser]:
    def dep(user: AdminUser = Depends(current_user)) -> AdminUser:
        if user.role not in roles:
            raise forbidden()
        return user

    return dep


require_editor = require_role(AdminRole.admin, AdminRole.editor)
require_admin = require_role(AdminRole.admin)
