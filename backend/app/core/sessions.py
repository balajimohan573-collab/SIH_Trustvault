"""DB-backed session management.

Replaces the in-memory demo store: sessions persist, are revocable, expire, and
are auditable. The access JWT is the bearer token; the `Session` row is the
source of truth checked on every authenticated request (see `deps.get_current_user`).
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session as SASession

from app.core.config import get_settings
from app.models import Session, User

log = logging.getLogger("trustvault.sessions")


def _now() -> datetime:
    # Naive UTC to stay consistent with SQLite storage and the rest of the app
    # (models use datetime.utcnow). Avoids offset-aware/naive comparison errors.
    return datetime.utcnow()


def create_session(
    db: SASession,
    user: User,
    jti: str,
    ip_addr: str | None = None,
    user_agent: str | None = None,
) -> Session:
    settings = get_settings()
    row = Session(
        user_id=user.id,
        jti=jti,
        expires_at=_now() + timedelta(hours=settings.session_ttl_hours),
        ip_addr=ip_addr,
        user_agent=user_agent,
    )
    db.add(row)
    db.flush()
    return row


def get_session(db: SASession, jti: str) -> Session | None:
    return db.query(Session).filter(Session.jti == jti).first()


def is_valid_session(db: SASession, jti: str) -> bool:
    row = get_session(db, jti)
    if row is None:
        return False
    if row.revoked_at is not None:
        return False
    if row.expires_at < _now():
        return False
    row.last_seen_at = _now()
    db.flush()
    return True


def revoke_session(db: SASession, jti: str, revoked_by: str | None = None) -> bool:
    row = get_session(db, jti)
    if row is None:
        return False
    row.revoked_at = _now()
    row.revoked_by = revoked_by
    db.flush()
    log.info("Session %s revoked", jti)
    return True


def revoke_sessions_for_user(db: SASession, user_id: str, revoked_by: str | None = None) -> int:
    rows = (
        db.query(Session)
        .filter(Session.user_id == user_id, Session.revoked_at.is_(None))
        .all()
    )
    for row in rows:
        row.revoked_at = _now()
        row.revoked_by = revoked_by
    db.flush()
    return len(rows)