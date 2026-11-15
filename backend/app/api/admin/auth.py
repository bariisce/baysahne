from fastapi import APIRouter, Depends, Request, Response
from pydantic import EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import client_ip, csrf_protect, current_session, current_user
from app.config import get_settings
from app.core.ratelimit import limiter
from app.db import get_db
from app.models import AdminSession, AdminUser
from app.schemas.common import StrictModel
from app.services import auth as auth_service

router = APIRouter(prefix="/api/v1/admin/auth", tags=["admin-auth"], dependencies=[Depends(csrf_protect)])


class LoginIn(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class PasswordIn(StrictModel):
    password: str = Field(min_length=1, max_length=256)


class TokenIn(StrictModel):
    token: str = Field(min_length=20, max_length=128)


class TokenPasswordIn(TokenIn):
    password: str = Field(min_length=1, max_length=256)


class ForgotIn(StrictModel):
    email: EmailStr


class ChangePasswordIn(StrictModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


def me_dict(u: AdminUser) -> dict:
    return {"id": str(u.id), "email": u.email, "full_name": u.full_name, "role": u.role.value}


def _set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        s.session_cookie_name,
        token,
        max_age=s.session_ttl_hours * 3600,
        httponly=True,
        secure=s.cookie_secure,
        samesite="strict",
        path="/",
    )


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = client_ip(request)
    limiter.hit(f"login:ip:{ip}", limit=20, window_seconds=300)
    limiter.hit(f"login:email:{body.email.lower()}", limit=10, window_seconds=300)
    user, token = auth_service.login(db, body.email, body.password, ip, request.headers.get("user-agent"))
    _set_cookie(response, token)
    return {"user": me_dict(user)}


@router.post("/logout", status_code=204)
def logout(response: Response, sess: AdminSession = Depends(current_session), db: Session = Depends(get_db)):
    auth_service.logout(db, sess)
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    response.status_code = 204
    return response


@router.get("/me")
def me(user: AdminUser = Depends(current_user)):
    return {"user": me_dict(user)}


@router.post("/password/change", status_code=204)
def change_password(body: ChangePasswordIn, request: Request, user: AdminUser = Depends(current_user),
                    db: Session = Depends(get_db)):
    limiter.hit(f"pwchange:{user.id}", limit=10, window_seconds=300)
    auth_service.change_password(db, user, body.current_password, body.new_password, client_ip(request))
    return Response(status_code=204)


@router.post("/password/forgot", status_code=202)
def forgot_password(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    limiter.hit(f"forgot:ip:{ip}", limit=10, window_seconds=900)
    limiter.hit(f"forgot:email:{body.email.lower()}", limit=3, window_seconds=900)
    auth_service.request_password_reset(db, body.email, ip)
    return {"message": "Bu adres kayıtlıysa parola sıfırlama bağlantısı gönderildi."}


# Tokens travel in the request body, never in the URL path, so they cannot end up in access logs.
# The e-mailed links put the token in the URL fragment (#...), which browsers never send to servers.


@router.post("/password/reset", status_code=204)
def reset_password(body: TokenPasswordIn, request: Request, db: Session = Depends(get_db)):
    limiter.hit(f"reset:ip:{client_ip(request)}", limit=10, window_seconds=900)
    auth_service.reset_password(db, body.token, body.password, client_ip(request))
    return Response(status_code=204)


@router.post("/invitations/inspect")
def inspect_invitation(body: TokenIn, request: Request, db: Session = Depends(get_db)):
    limiter.hit(f"invite:ip:{client_ip(request)}", limit=30, window_seconds=900)
    inv = auth_service.inspect_invitation(db, body.token)
    return {"email": inv.email, "full_name": inv.full_name, "role": inv.role.value,
            "expires_at": inv.expires_at.isoformat()}


@router.post("/invitations/accept")
def accept_invitation(body: TokenPasswordIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = client_ip(request)
    limiter.hit(f"invite:ip:{ip}", limit=30, window_seconds=900)
    user = auth_service.accept_invitation(db, body.token, body.password, ip)
    _, session_token = auth_service.login(db, user.email, body.password, ip, request.headers.get("user-agent"))
    _set_cookie(response, session_token)
    return {"user": me_dict(user)}
