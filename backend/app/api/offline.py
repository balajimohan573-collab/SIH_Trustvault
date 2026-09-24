"""Offline capability (V2) — queue, dedupe, sync.

Flights/field offices without connectivity: a decision made offline is stored
locally, then reconciled with the audit trail on the next sync. Re-uploads are
idempotent via `content_hash` (AppendModel pattern: retries must not double-
count).
"""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.crypto import sha256_hex
from app.db.session import get_db
from app.models import OfflineEvent, User
from app.schemas import OfflineBatchIn, OfflineEventOut, OfflineSyncOut
from app.services import audit

router = APIRouter(prefix="/offline", tags=["offline"])
log = logging.getLogger("trustvault.offline")


def _content_hash(event: dict) -> str:
    canonical = sorted(event.items())
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return sha256_hex(blob)


@router.post("/queue", response_model=OfflineSyncOut)
def queue_offline(
    body: OfflineBatchIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ingest offline decisions, deduping by content hash (idempotent)."""
    received = 0
    synced = 0
    deduped = 0
    failed = 0
    for ev in body.events:
        received += 1
        event = ev.model_dump()
        chash = _content_hash(event.get("payload", {}))
        existing = db.query(OfflineEvent).filter(OfflineEvent.content_hash == chash).first()
        if existing:
            deduped += 1
            continue
        row = OfflineEvent(
            user_id=current.id,
            asset_id=ev.asset_id,
            event_type=ev.event_type,
            decision=ev.decision,
            reasons=ev.reasons,
            trust_score=ev.trust_score,
            payload=ev.payload,
            content_hash=chash,
            client_ts=ev.client_ts or datetime.utcnow(),
            sync_status="pending",
        )
        db.add(row)
        synced += 1
    db.commit()
    log.info("Offline ingest: received=%d synced=%d deduped=%d", received, synced, deduped)
    return OfflineSyncOut(received=received, synced=synced, deduped=deduped, failed=0)


@router.post("/sync", response_model=OfflineSyncOut)
def sync_offline(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Anchor pending offline events into the tamper-evident audit trail."""
    pending = db.query(OfflineEvent).filter(OfflineEvent.sync_status == "pending").all()
    synced = 0
    for ev in pending:
        audit.anchor(
            db,
            "offline_sync",
            user_id=current.id,
            risk={
                "event_id": ev.id,
                "event_type": ev.event_type,
                "decision": ev.decision,
                "asset_id": ev.asset_id,
                "client_ts": ev.client_ts.isoformat() if ev.client_ts else None,
            },
        )
        ev.sync_status = "synced"
        synced += 1
    db.commit()
    log.info("Offline sync anchored %d event(s)", synced)
    return OfflineSyncOut(received=len(pending), synced=synced, deduped=0, failed=0)


@router.get("/events", response_model=list[OfflineEventOut])
def list_offline_events(
    current: User = Depends(require_role("auditor", "admin")),
    db: Session = Depends(get_db),
):
    """List offline events (auditor/admin)."""
    rows = db.query(OfflineEvent).order_by(OfflineEvent.created_at.desc()).limit(200).all()
    return [
        OfflineEventOut(
            id=r.id,
            event_type=r.event_type,
            asset_id=r.asset_id,
            decision=r.decision,
            trust_score=r.trust_score,
            sync_status=r.sync_status,
            created_at=r.created_at,
        )
        for r in rows
    ]