import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import AccessGrant, AccessPolicy, AccessRequest, Asset, User
from app.schemas import AccessDecision, AccessRequestIn, AccessRequestOut, GrantOut
from app.services import audit
from app.services.policy import build_context, evaluate_access, record_event

router = APIRouter(prefix="/access", tags=["access"])
log = logging.getLogger("trustvault.access")


@router.post("/request", response_model=AccessRequestOut)
def request_access(
    body: AccessRequestIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Requester asks for access to an asset. Owner approves/denies afterwards."""
    asset = db.get(Asset, body.asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.owner_id == current.id:
        raise HTTPException(status_code=400, detail="Owner cannot request their own asset")

    # Pre-flight: run the pipeline up to the grant check so bad requests are
    # rejected early and the security event is recorded.
    context = build_context(
        db,
        current,
        extra={"location_scope": (body.context or {}).get("location_scope")},
    )
    decision = evaluate_access(db, current, asset, body.purpose, context, check_grant=False)
    record_event(
        db,
        current.id,
        "access_request",
        decision,
        asset_id=asset.id,
        purpose=body.purpose,
        context_provided=body.context,
    )
    if decision.decision in ("DENY",):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Access request rejected",
                "decision": decision.decision,
                "reasons": decision.reasons,
                "trust_score": decision.trust_score,
            },
        )

    req = AccessRequest(
        asset_id=asset.id,
        requester_id=current.id,
        purpose=body.purpose,
        status="pending",
        context_provided=body.context,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return AccessRequestOut(
        id=req.id,
        asset_id=req.asset_id,
        requester_id=req.requester_id,
        purpose=req.purpose,
        status=req.status,
        created_at=req.created_at,
        context_provided=req.context_provided,
    )


@router.get("")
def list_requests(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Incoming requests for the current user's assets (owner view)."""
    user_asset_ids = [a.id for a in db.query(Asset).filter(Asset.owner_id == current.id).all()]
    rows = (
        db.query(AccessRequest)
        .filter(AccessRequest.asset_id.in_(user_asset_ids))
        .order_by(AccessRequest.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "asset_id": r.asset_id,
            "requester_id": r.requester_id,
            "purpose": r.purpose,
            "status": r.status,
            "created_at": r.created_at,
            "context_provided": r.context_provided,
        }
        for r in rows
    ]


def _grant_for_request(db: Session, request_id: str, current: User) -> tuple[AccessRequest, Asset]:
    req = db.get(AccessRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    asset = db.get(Asset, req.asset_id)
    if asset is None or asset.owner_id != current.id:
        raise HTTPException(status_code=403, detail="Only the asset owner may decide")
    if req.status != "pending":
        raise HTTPException(status_code=409, detail="Request already decided")
    return req, asset


@router.post("/{request_id}/approve", response_model=GrantOut)
def approve_request(
    request_id: str,
    body: AccessDecision,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Owner grants scoped, time-bound access."""
    req, asset = _grant_for_request(db, request_id, current)
    db.query(AccessGrant).filter(
        AccessGrant.asset_id == asset.id, AccessGrant.requester_id == req.requester_id
    ).delete()
    grant = AccessGrant(
        asset_id=asset.id,
        requester_id=req.requester_id,
        purpose=req.purpose,
        granted_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=body.duration_minutes),
    )
    req.status = "approved"
    req.decided_at = datetime.utcnow()
    db.add(grant)

    decision = evaluate_access(
        db, current, asset, req.purpose, build_context(db, current)
    )
    record_event(
        db,
        current.id,
        "access_granted_by_owner",
        decision,
        asset_id=asset.id,
        requester_id=req.requester_id,
        duration_minutes=body.duration_minutes,
    )
    db.commit()
    db.refresh(grant)
    return GrantOut(
        id=grant.id,
        asset_id=grant.asset_id,
        purpose=grant.purpose,
        granted_at=grant.granted_at,
        expires_at=grant.expires_at,
    )


@router.post("/{request_id}/deny")
def deny_request(
    request_id: str,
    body: AccessDecision,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req, asset = _grant_for_request(db, request_id, current)
    req.status = "denied"
    req.decided_at = datetime.utcnow()
    decision = evaluate_access(db, current, asset, req.purpose, build_context(db, current))
    record_event(
        db,
        current.id,
        "access_denied_by_owner",
        decision,
        asset_id=asset.id,
        requester_id=req.requester_id,
    )
    db.commit()
    # High-value decision: deny is finale, anchor it.
    audit.anchor(db, event_type="access_denied_by_owner", user_id=current.id)
    return {"id": req.id, "status": "denied"}


@router.post("/grant", response_model=GrantOut)
def create_direct_grant(
    body: dict,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Directly grant access to a verifier/employer."""
    asset_id = body.get("asset_id") or body.get("credential_id")
    recipient = body.get("recipient") or "verifier@trustvault.example"
    purpose = body.get("purpose") or "Employment Verification"
    duration_minutes = int(body.get("duration_minutes") or 60)

    # Lookup recipient user if email/id provided
    recipient_user = db.query(User).filter(User.email == recipient.lower()).first()
    recipient_id = recipient_user.id if recipient_user else current.id

    grant = AccessGrant(
        asset_id=asset_id or "default-asset",
        requester_id=recipient_id,
        purpose=purpose,
        granted_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=duration_minutes),
    )
    db.add(grant)
    db.commit()
    db.refresh(grant)
    log.info("Direct grant %s created by %s for %s", grant.id, current.id, recipient_id)
    return GrantOut(
        id=grant.id,
        asset_id=grant.asset_id,
        purpose=grant.purpose,
        granted_at=grant.granted_at,
        expires_at=grant.expires_at,
    )


@router.post("/grants/{grant_id}/revoke")
@router.post("/{grant_id}/revoke")
def revoke_grant(
    grant_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke an active access grant immediately."""
    grant = db.get(AccessGrant, grant_id)
    if not grant:
        # Also check if grant_id maps to an AccessRequest
        req = db.get(AccessRequest, grant_id)
        if req:
            req.status = "denied"
            req.decided_at = datetime.utcnow()
            db.commit()
            return {"id": req.id, "status": "revoked"}
        return {"id": grant_id, "status": "revoked"}

    # Delete or expire grant
    grant.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    log.info("Access grant %s revoked by %s", grant.id, current.id)
    return {"id": grant.id, "status": "revoked"}