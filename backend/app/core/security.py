import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()  # Argon2id with library defaults (RFC 9106 low-memory profile)

# Verifying against this keeps login timing similar for unknown e-mails.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))

MIN_PASSWORD_LENGTH = 10


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def validate_password(password: str, email: str | None = None) -> str | None:
    """Return a Turkish error message, or None if acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Parola en az {MIN_PASSWORD_LENGTH} karakter olmalıdır."
    if len(password) > 256:
        return "Parola çok uzun."
    if len(set(password)) < 4:
        return "Parola çok basit; farklı karakterler kullanın."
    if email and email.split("@")[0].lower() in password.lower() and len(email.split("@")[0]) >= 4:
        return "Parola e-posta adresinizi içermemelidir."
    return None


def new_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hex). Only the hash is ever persisted."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
