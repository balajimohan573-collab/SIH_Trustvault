"""Duress mode (V2) — covert freeze of sensitive access.

Disabled by default (`duress_enabled`). When on, a user can flag that they are
acting under coercion; the platform then freezes sensitive operations
(STEP_UP/DENY bias) so a forced actor cannot exfiltrate data. The session is
short-lived and leaves a clear audit trail.
"""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import DuressSession, User
from app.services import audit

router = APIRouter(prefix="/duress", tags=["duress"])
log = logging.getLogger("trustvault.duress")


def _require_enabled() -> None:
    if not get_settings().duress_enabled:
        raise HTTPException(status_code=400, detail="Duress mode is disabled on this deployment")


@router.get("/status")
def duress_status(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(DuressSession)
        .filter(DuressSession.user_id == current.id)
        .order_by(DuressSession.activated_at.desc())
        .first()
    )
    if session and session.active and session.expires_at and session.expires_at < datetime.utcnow():
        session.active = False
        db.commit()
    return {"active": bool(session and session.active), "id": session.id if session else None}


@router.post("/activate")
def activate_duress(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Covertly flag duress. Sensitive access is frozen for a short TTL."""
    _require_enabled()
    ttl = timedelta(minutes=get_settings().duress_ttl_minutes)
    session = DuressSession(
        user_id=current.id,
        active=True,
        activated_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + ttl,
    )
    db.add(session)
    db.commit()
    audit.anchor(
        db,
        "duress",
        user_id=current.id,
        risk={"session_id": session.id, "action": "activate"},
    )
    log.warning("Duress activated for %s (%s)", current.id, session.id)
    return {
        "id": session.id,
        "active": session.active,
        "expires_at": session.expires_at,
        "note": "Sensitive access is frozen until expiry. A silent alert has been recorded.",
    }


@router.post("/deactivate")
def deactivate_duress(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_enabled()
    session = (
        db.query(DuressSession)
        .filter(DuressSession.user_id == current.id, DuressSession.active.is_(True))
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="No active duress session")
    session.active = False
    db.commit()
    audit.anchor(
        db,
        "duress",
        user_id=current.id,
        risk={"session_id": session.id, "action": "deactivate"},
    )
    return {"id": session.id, "active": False}