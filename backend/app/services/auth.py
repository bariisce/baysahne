from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import AppError, bad_request, conflict
from app.core.security import (
    hash_password,
    hash_token,
    needs_rehash,
    new_token,
    validate_password,
    verify_password,
)
from app.core.text import utcnow
from app.models import AdminInvitation, AdminRole, AdminSession, AdminUser, PasswordResetToken
from app.services import audit, mailer

INVALID_LOGIN = "E-posta adresi veya parola hatalı."


def normalize_email(email: str) -> str:
    return email.strip().lower()


# ---------------------------------------------------------------- sessions


def login(db: Session, email: str, password: str, ip: str | None, user_agent: str | None) -> tuple[AdminUser, str]:
    s = get_settings()
    email = normalize_email(email)
    user = db.scalar(select(AdminUser).where(AdminUser.email == email))
    now = utcnow()

    if user and user.locked_until and user.locked_until > now:
        verify_password(None, password)  # keep timing uniform
        raise AppError(
            423, "account_locked", "Çok sayıda hatalı deneme nedeniyle hesap geçici olarak kilitlendi. "
            "Lütfen daha sonra tekrar deneyin veya parolanızı sıfırlayın."
        )

    ok = verify_password(user.password_hash if user else None, password)
    if not user or not ok or not user.is_active:
        if user and not ok:
            user.failed_login_count += 1
            if user.failed_login_count >= s.max_failed_logins:
                user.locked_until = now + timedelta(minutes=s.lockout_minutes)
                user.failed_login_count = 0
                audit.record(db, user, "auth.locked", entity_type="admin_user", entity_id=user.id, ip=ip,
                             summary="Hesap çok sayıda hatalı giriş nedeniyle kilitlendi")
        audit.record(db, None, "auth.login_failed", summary=f"Başarısız giriş: {email}", ip=ip)
        db.commit()
        raise AppError(401, "invalid_credentials", INVALID_LOGIN)

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    raw, digest = new_token()
    db.add(
        AdminSession(
            user_id=user.id,
            token_hash=digest,
            expires_at=now + timedelta(hours=s.session_ttl_hours),
            last_seen_at=now,
            ip=ip,
            user_agent=(user_agent or "")[:300] or None,
        )
    )
    audit.record(db, user, "auth.login", entity_type="admin_user", entity_id=user.id, ip=ip)
    db.commit()
    return user, raw


def resolve_session(db: Session, raw_token: str) -> AdminSession | None:
    now = utcnow()
    sess = db.scalar(select(AdminSession).where(AdminSession.token_hash == hash_token(raw_token)))
    if not sess or sess.revoked_at or sess.expires_at <= now or not sess.user.is_active:
        return None
    # Touch at most once a minute to avoid a write per request.
    if not sess.last_seen_at or (now - sess.last_seen_at).total_seconds() > 60:
        sess.last_seen_at = now
        db.commit()
    return sess


def logout(db: Session, sess: AdminSession) -> None:
    sess.revoked_at = utcnow()
    audit.record(db, sess.user, "auth.logout", entity_type="admin_user", entity_id=sess.user_id)
    db.commit()


def revoke_all_sessions(db: Session, user_id) -> None:
    db.execute(
        update(AdminSession)
        .where(AdminSession.user_id == user_id, AdminSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


# ---------------------------------------------------------------- invitations


def create_invitation(
    db: Session, *, email: str, full_name: str, role: AdminRole, invited_by: AdminUser | None, ip: str | None = None
) -> tuple[AdminInvitation, str]:
    s = get_settings()
    email = normalize_email(email)
    if db.scalar(select(AdminUser).where(AdminUser.email == email)):
        raise conflict("user_exists", "Bu e-posta adresiyle kayıtlı bir yönetici zaten var.")
    now = utcnow()
    # Any older open invitation for the same address is superseded.
    db.execute(
        update(AdminInvitation)
        .where(
            AdminInvitation.email == email,
            AdminInvitation.accepted_at.is_(None),
            AdminInvitation.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    raw, digest = new_token()
    inv = AdminInvitation(
        email=email,
        full_name=full_name.strip(),
        role=role,
        token_hash=digest,
        invited_by_id=invited_by.id if invited_by else None,
        expires_at=now + timedelta(hours=s.invitation_ttl_hours),
    )
    db.add(inv)
    db.flush()
    audit.record(db, invited_by, "admin.invite", entity_type="admin_invitation", entity_id=inv.id, ip=ip,
                 summary=f"{full_name} ({email}) {role.value} olarak davet edildi", details={"role": role.value})
    return inv, raw


def invitation_link(raw: str) -> str:
    return f"{get_settings().admin_base_url.rstrip('/')}/davet#{raw}"


def reset_link(raw: str) -> str:
    return f"{get_settings().admin_base_url.rstrip('/')}/parola-sifirla/yeni#{raw}"


def send_invitation(inv: AdminInvitation, raw: str, inviter: AdminUser | None) -> None:
    mailer.invitation_mail(
        inv.email, inv.full_name, inviter.full_name if inviter else None, invitation_link(raw),
        get_settings().invitation_ttl_hours,
    )


def _open_invitation(db: Session, raw: str) -> AdminInvitation:
    inv = db.scalar(select(AdminInvitation).where(AdminInvitation.token_hash == hash_token(raw)))
    if not inv or inv.revoked_at or inv.accepted_at or inv.expires_at <= utcnow():
        raise bad_request("invalid_invitation",
                          "Davet bağlantısı geçersiz veya süresi dolmuş. Yöneticinizden yeni bir davet isteyin.")
    return inv


def inspect_invitation(db: Session, raw: str) -> AdminInvitation:
    return _open_invitation(db, raw)


def accept_invitation(db: Session, raw: str, password: str, ip: str | None) -> AdminUser:
    inv = _open_invitation(db, raw)
    if err := validate_password(password, inv.email):
        raise bad_request("weak_password", err)
    if db.scalar(select(AdminUser).where(AdminUser.email == inv.email)):
        raise conflict("user_exists", "Bu e-posta adresiyle kayıtlı bir yönetici zaten var.")
    now = utcnow()
    user = AdminUser(
        email=inv.email,
        full_name=inv.full_name,
        role=inv.role,
        password_hash=hash_password(password),
        is_active=True,
        password_changed_at=now,
    )
    db.add(user)
    db.flush()
    inv.accepted_at = now
    inv.user_id = user.id
    audit.record(db, user, "admin.invitation_accepted", entity_type="admin_user", entity_id=user.id, ip=ip)
    db.commit()
    return user


# ---------------------------------------------------------------- password reset


def request_password_reset(db: Session, email: str, ip: str | None) -> None:
    """Always behaves the same whether or not the address exists (no account enumeration)."""
    s = get_settings()
    user = db.scalar(select(AdminUser).where(AdminUser.email == normalize_email(email)))
    if not user or not user.is_active:
        return
    now = utcnow()
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    raw, digest = new_token()
    db.add(PasswordResetToken(user_id=user.id, token_hash=digest,
                              expires_at=now + timedelta(minutes=s.password_reset_ttl_minutes)))
    audit.record(db, user, "auth.password_reset_requested", entity_type="admin_user", entity_id=user.id, ip=ip)
    db.commit()
    mailer.password_reset_mail(user.email, user.full_name, reset_link(raw), s.password_reset_ttl_minutes)


def reset_password(db: Session, raw: str, password: str, ip: str | None) -> None:
    tok = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw)))
    if not tok or tok.used_at or tok.expires_at <= utcnow():
        raise bad_request("invalid_reset_token", "Parola sıfırlama bağlantısı geçersiz veya süresi dolmuş.")
    user = db.get(AdminUser, tok.user_id)
    if not user or not user.is_active:
        raise bad_request("invalid_reset_token", "Parola sıfırlama bağlantısı geçersiz veya süresi dolmuş.")
    if err := validate_password(password, user.email):
        raise bad_request("weak_password", err)
    now = utcnow()
    tok.used_at = now
    user.password_hash = hash_password(password)
    user.password_changed_at = now
    user.failed_login_count = 0
    user.locked_until = None
    revoke_all_sessions(db, user.id)
    audit.record(db, user, "auth.password_reset", entity_type="admin_user", entity_id=user.id, ip=ip)
    db.commit()


def change_password(db: Session, user: AdminUser, current: str, new: str, ip: str | None) -> None:
    if not verify_password(user.password_hash, current):
        raise bad_request("invalid_password", "Mevcut parola hatalı.")
    if err := validate_password(new, user.email):
        raise bad_request("weak_password", err)
    user.password_hash = hash_password(new)
    user.password_changed_at = utcnow()
    audit.record(db, user, "auth.password_changed", entity_type="admin_user", entity_id=user.id, ip=ip)
    db.commit()
