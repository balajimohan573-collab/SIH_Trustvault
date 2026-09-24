"""Short-lived QR verification tokens (V2).

Signature covers credential_id + purpose so an attacker cannot swap the token
onto a different credential. Tokens carry scope="credential_verify" to keep them
distinct from auth JWTs, and expire after a few minutes (configurable).
"""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()

_SCOPE = "credential_verify"


def create_qr_token(credential_id: str, purpose: str | None, expires_minutes: int | None = None) -> tuple[str, datetime]:
    minutes = expires_minutes or settings.qr_expiry_minutes
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {
        "sub": credential_id,
        "scope": _SCOPE,
        "purpose": purpose,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.algorithm), expires_at


def verify_qr_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.algorithm])
    except JWTError:
        return None
    if payload.get("scope") != _SCOPE:
        return None
    return payload