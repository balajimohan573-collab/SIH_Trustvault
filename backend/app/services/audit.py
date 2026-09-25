"""Audit anchoring queue.

Stage 6 wires the actual on-chain transaction on the configured network. Until
then anchors are recorded as `pending` rows so every high-value event is
captured and promotable.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuditAnchor, SecurityEvent

log = logging.getLogger("trustvault.audit")

# Event types that warrant on-chain anchoring (high value only).
ANCHORABLE_EVENTS = {
    "credential_issued",
    "credential_revoked",
    "asset_created",
    "asset_minted",
    "asset_transferred",
    "access_granted_by_owner",
    "access_denied_by_owner",
    "access_allowed",
    "access_denied",
    "admin_override",
    "duress_activated",
    "device_revoked",
    "device_recovery_requested",
    "device_recovery_approved",
    "device_recovery_denied",
    "offline_sync",
}


def anchor(
    db: Session,
    event_type: str,
    user_id: str | None = None,
    event_id: str | None = None,
    risk: dict | None = None,
) -> AuditAnchor | None:
    """Create a pending anchor for a high-value event (no-op for telemetry)."""
    if event_type not in ANCHORABLE_EVENTS:
        return None
    if event_id is None:
        evt = SecurityEvent(
            user_id=user_id,
            event_type=event_type,
            risk_signals=risk or {},
        )
        db.add(evt)
        db.flush()
        event_id = evt.id
    anchor_row = AuditAnchor(
        id=str(uuid.uuid4()),
        event_id=event_id,
        tx_hash="pending",
        chain=get_settings().chain_network,
        anchored_at=datetime.now(timezone.utc),
    )
    db.add(anchor_row)
    db.commit()
    log.info("Anchor created (pending) for event %s", event_id)
    return anchor_row


def attach_tx(db: Session, event_id: str, tx_hash: str) -> AuditAnchor | None:
    row = db.query(AuditAnchor).filter(AuditAnchor.event_id == event_id).first()
    if row:
        row.tx_hash = tx_hash
        row.anchored_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
    return row