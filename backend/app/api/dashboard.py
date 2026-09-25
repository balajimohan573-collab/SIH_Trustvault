"""Dashboard summary (V2) — role-scoped aggregates + technical view.

Responsible for one thing: turning raw tables into the exact shape the frontend
needs, respecting role boundaries so a holder never sees admin counters and
vice-versa.
"""
import logging
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    AccessGrant,
    AccessRequest,
    Asset,
    Credential,
    OfflineEvent,
    SecurityEvent,
    TrustedDevice,
    User,
)
from app.schemas import DashboardSummary
from app.services.trust import MODEL_VERSION

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
log = logging.getLogger("trustvault.dashboard")


@router.get("/summary", response_model=DashboardSummary)
def summary(
    technical: bool = False,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agg = DashboardSummary(user_role=current.role)
    _identities(db, agg, current)
    _credentials(db, agg, current)
    _assets(db, agg, current)
    _requests(db, agg, current)
    _activity(db, agg, current)
    _trust(db, agg, current)
    if technical:
        agg.technical = _technical_view(db, current)
    return agg


def _identities(db: Session, agg: DashboardSummary, me: User) -> None:
    if me.role == "admin":
        agg.identities = {
            "total_users": db.query(User).count(),
            "active_users": db.query(User).filter(User.status == "active").count(),
            "registered_devices": db.query(TrustedDevice).count(),
        }
    else:
        agg.identities = {"my_did": me.did}


def _credentials(db: Session, agg: DashboardSummary, me: User) -> None:
    if me.role in ("issuer", "admin"):
        payload = {
            "issued_total": db.query(Credential).filter(Credential.issuer_user_id == me.id).count(),
            "issued_active": db.query(Credential)
            .filter(Credential.issuer_user_id == me.id, Credential.status == "active")
            .count(),
            "issued_revoked": db.query(Credential)
            .filter(Credential.issuer_user_id == me.id, Credential.status == "revoked")
            .count(),
            "types": _type_breakdown(db, Credential.issuer_user_id == me.id),
        }
    else:
        payload = {
            "held_total": db.query(Credential).filter(Credential.holder_id == me.id).count(),
            "held_active": db.query(Credential)
            .filter(Credential.holder_id == me.id, Credential.status == "active")
            .count(),
            "held_revoked": db.query(Credential)
            .filter(Credential.holder_id == me.id, Credential.status == "revoked")
            .count(),
            "types": _type_breakdown(db, Credential.holder_id == me.id),
        }
    agg.credentials = payload


def _assets(db: Session, agg: DashboardSummary, me: User) -> None:
    owned = db.query(Asset).filter(Asset.owner_id == me.id)
    agg.assets = {
        "owned_total": owned.count(),
        "owned": owned.count(),  # alias for the Technical panel
        "granted_to_me": (
            db.query(AccessGrant).filter(AccessGrant.requester_id == me.id).count()
        ),
        "nft_minted": owned.filter(Asset.nft_token_id.isnot(None)).count(),
    }


def _requests(db: Session, agg: DashboardSummary, me: User) -> None:
    if me.role in ("admin", "auditor"):
        rows = db.query(AccessRequest).filter(AccessRequest.status == "pending").all()
    else:
        my_asset_ids = [aid for (aid,) in db.query(Asset.id).filter(Asset.owner_id == me.id).all()]
        rows = (
            db.query(AccessRequest)
            .filter(AccessRequest.status == "pending", AccessRequest.asset_id.in_(my_asset_ids))
            .all()
        )
    agg.pending_requests = [
        {
            "id": r.id,
            "asset_id": r.asset_id,
            "requester_id": r.requester_id,
            "purpose": r.purpose,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


def _activity(db: Session, agg: DashboardSummary, me: User) -> None:
    events = _recent_events(db, me)
    agg.recent_activity = [
        {
            "id": e.id,
            "event_type": e.event_type,
            "decision": e.decision,
            "trust_score": e.trust_score,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


def _trust(db: Session, agg: DashboardSummary, me: User) -> None:
    latest = db.query(SecurityEvent).filter(SecurityEvent.user_id == me.id).order_by(SecurityEvent.created_at.desc()).first()
    agg.trust = {
        "model_version": MODEL_VERSION,
        "current_score": latest.trust_score if latest else None,
        "weeks_no_incident": None,  # computed by rules engine, not persisted
    }


def _recent_events(db: Session, me: User, limit: int = 8):
    mine = db.query(SecurityEvent).filter(SecurityEvent.user_id == me.id)
    if me.role in ("admin", "auditor"):
        return db.query(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(limit).all()
    return mine.order_by(SecurityEvent.created_at.desc()).limit(limit).all()


def _type_breakdown(db: Session, condition):
    rows = db.query(Credential.type, Credential.status).filter(condition).all()
    return dict(Counter(f"{t}:{s}" for t, s in rows))


def _technical_view(db: Session, me: User) -> dict:
    s = get_settings()
    return {
        "flags": {
            "chain_enabled": s.chain_enabled,
            "offline_enabled": s.offline_enabled,
            "duress_enabled": s.duress_enabled,
            "qr_expiry_minutes": s.qr_expiry_minutes,
            "ml_anomaly": s.ml_anomaly_enabled,
        },
        "counts": {
            "users": db.query(User).count(),
            "credentials": db.query(Credential).count(),
            "assets": db.query(Asset).count(),
            "pending_requests": db.query(AccessRequest).filter(AccessRequest.status == "pending").count(),
            "offline_pending": db.query(OfflineEvent).filter(OfflineEvent.sync_status == "pending").count(),
        },
        "chain": {
            "asset_registry": s.asset_registry_address,
            "audit_registry": s.audit_registry_address,
            "rpc_configured": bool(s.rpc_url),
        },
    }