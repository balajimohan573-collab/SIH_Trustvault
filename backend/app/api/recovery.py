"""Device recovery (V2) — request a new device / revoke a lost one.

A lost device is a first-class security event: it is recorded in the audit
trail, the user enrolls a replacement, and admins/issuers approve or deny the
request.
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models import DeviceRecovery, User
from app.schemas import DeviceRecoverOut, DeviceRecoverRequest
from app.services import audit

router = APIRouter(prefix="/recovery", tags=["recovery"])
log = logging.getLogger("trustvault.recovery")


@router.post("/request", response_model=DeviceRecoverOut)
def request_recovery(
    body: DeviceRecoverRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Holder reports device loss / requests a replacement."""
    row = DeviceRecovery(
        user_id=current.id,
        status="pending",
        reason=body.reason,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    audit.anchor(
        db,
        "device_recovery",
        user_id=current.id,
        risk={"request_id": row.id, "status": row.status},
    )
    log.warning("Device recovery requested by %s (%s)", current.id, body.reason)
    return DeviceRecoverOut(
        id=row.id,
        user_id=row.user_id,
        status=row.status,
        reason=row.reason,
        requested_at=row.requested_at,
    )


@router.get("", response_model=list[DeviceRecoverOut])
def list_recoveries(
    current: User = Depends(require_role("admin", "auditor", "issuer", "verifier")),
    db: Session = Depends(get_db),
):
    if current.role in ("admin", "auditor"):
        rows = db.query(DeviceRecovery).order_by(DeviceRecovery.requested_at.desc()).all()
    else:
        rows = db.query(DeviceRecovery).filter(DeviceRecovery.user_id == current.id).all()
    return [
        DeviceRecoverOut(
            id=r.id,
            user_id=r.user_id,
            status=r.status,
            reason=r.reason,
            requested_at=r.requested_at,
        )
        for r in rows
    ]


@router.post("/{recovery_id}/decide", response_model=DeviceRecoverOut)
def decide_recovery(
    recovery_id: str,
    status: str,
    current: User = Depends(require_role("admin", "issuer")),
    db: Session = Depends(get_db),
):
    """Admin/issuer approves or denies the recovery request."""
    if status not in ("approved", "denied"):
        raise HTTPException(status_code=400, detail="Status must be 'approved' or 'denied'")
    row = db.get(DeviceRecovery, recovery_id)
    if not row:
        raise HTTPException(status_code=404, detail="Recovery request not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="Recovery already decided")
    row.status = status
    row.decided_at = datetime.utcnow()
    db.commit()
    audit.anchor(
        db,
        "device_recovery",
        user_id=current.id,
        risk={"request_id": row.id, "decision": status},
    )
    return DeviceRecoverOut(
        id=row.id,
        user_id=row.user_id,
        status=row.status,
        reason=row.reason,
        requested_at=row.requested_at,
    )