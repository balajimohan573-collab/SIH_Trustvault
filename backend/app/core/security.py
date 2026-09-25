"""Password hashing, JWT issuance and short-lived scoped tokens.

The JWT carries a `jti`; the *authoritative* session state lives in the DB
(`sessions` table) so sessions survive restarts, can be revoked server-side and
are auditably attributable. `scope` keeps token types distinct so a QR or
password-reset token can never authenticate as a session.
"""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    return pwd_context.verify(plain, hashed)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(subject: str, extra: dict | None = None) -> str:
    payload: dict = {
        "sub": subject,
        "type": "access",
        "exp": _now() + timedelta(minutes=settings.jwt_expiry_minutes),
        "iat": _now(),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.algorithm])
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload


def create_password_reset_token(email: str) -> tuple[str, datetime]:
    expires_at = _now() + timedelta(minutes=30)
    payload = {
        "sub": email.lower(),
        "type": "password_reset",
        "scope": "password_reset",
        "exp": expires_at,
        "iat": _now(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.algorithm), expires_at


def decode_password_reset_token(token: str) -> str | None:
    """Return the email bound to a valid reset token, else None."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.algorithm])
    except JWTError:
        return None
    if payload.get("type") != "password_reset" or payload.get("scope") != "password_reset":
        return None
    email = payload.get("sub")
    return email if isinstance(email, str) else None