"""Purpose-bound credential access.

A verifier requests access to *permitted claims* of a credential for a stated
purpose (with an expiry). The holder approves/denies. Grants are enforced
server-side on every `/content` fetch: status, purpose, allowed-claim allowlist
and expiry are all re-checked, and the holder can revoke instantly.
"""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import (
    Credential,
    CredentialAccessGrant,
    CredentialAccessRequest,
    Notification,
    User,
)
from app.schemas import (
    CredentialAccessDecision,
    CredentialAccessGrantOut,
    CredentialAccessRequestIn,
    CredentialAccessRequestOut,
    CredentialContentOut,
)
from app.services import audit_trail

router = APIRouter(prefix="/access/credential", tags=["credential-access"])
log = logging.getLogger("trustvault.credential_access")


@router.post("/request", response_model=CredentialAccessRequestOut)
def request_credential_access(
    body: CredentialAccessRequestIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """A verifier requests claim access for a purpose. Holder decides."""
    credential = db.get(Credential, body.credential_id)
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    if credential.holder_id == current.id:
        raise HTTPException(status_code=400, detail="The holder cannot request their own credential")
    if credential.status != "active":
        raise HTTPException(status_code=400, detail="Only active credentials can be shared")

    # Bound the requested claims to claims that actually exist on the credential.
    available = {c.claim_key for c in credential.claims}
    for key in body.requested_claims:
        if key not in available:
            raise HTTPException(status_code=400, detail=f"Requested claim '{key}' does not exist on this credential")

    row = CredentialAccessRequest(
        credential_id=credential.id,
        requester_id=current.id,
        purpose=body.purpose,
        requested_claims=body.requested_claims,
        expires_at=datetime.utcnow() + timedelta(minutes=body.expires_minutes),
    )
    db.add(row)
    db.flush()
    # Notify the holder in-app so they can approve/deny without polling.
    db.add(
        Notification(
            user_id=credential.holder_id,
            type="access_request",
            title="New access request",
            body=f"{current.full_name or current.email} requests claim access for '{body.purpose}'.",
            link=f"/access?request={row.id}",
        )
    )
    audit_trail.record(
        db, current.id, "credential_access_requested", "credential", credential.id,
        metadata={"purpose": body.purpose, "claims": body.requested_claims},
    )
    db.commit()
    db.refresh(row)
    return _req_out(row)


@router.get("/requests", response_model=list[CredentialAccessRequestOut])
def list_credential_requests(
    scope: str = "incoming",  # incoming (holder) | outgoing (verifier) | pending
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cred_ids = [c.id for c in db.query(Credential).filter(Credential.holder_id == current.id).all()]
    q = db.query(CredentialAccessRequest)
    if scope == "incoming":
        q = q.filter(CredentialAccessRequest.status == "pending", CredentialAccessRequest.credential_id.in_(cred_ids))
    elif scope == "outgoing":
        q = q.filter(CredentialAccessRequest.requester_id == current.id)
    else:
        q = q.filter(CredentialAccessRequest.credential_id.in_(cred_ids))
    return [_req_out(r) for r in q.order_by(CredentialAccessRequest.created_at.desc()).all()]


@router.get("/grants", response_model=list[CredentialAccessGrantOut])
def list_my_grants(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Grants I received (requester view). The holder views theirs via /grants/all."""
    rows = (
        db.query(CredentialAccessGrant)
        .filter(CredentialAccessGrant.requester_id == current.id)
        .order_by(CredentialAccessGrant.granted_at.desc())
        .all()
    )
    return [_grant_out(g) for g in rows]


@router.get("/grants/all", response_model=list[CredentialAccessGrantOut])
def holder_grants(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Active + historical grants on credentials I hold (holder view)."""
    cred_ids = [c.id for c in db.query(Credential).filter(Credential.holder_id == current.id).all()]
    rows = (
        db.query(CredentialAccessGrant)
        .filter(CredentialAccessGrant.credential_id.in_(cred_ids))
        .order_by(CredentialAccessGrant.granted_at.desc())
        .all()
    )
    return [_grant_out(g) for g in rows]


def _grant_for_request(db: Session, request_id: str, holder: User) -> CredentialAccessRequest:
    req = db.get(CredentialAccessRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    cred = db.get(Credential, req.credential_id)
    if not cred or cred.holder_id != holder.id:
        raise HTTPException(status_code=403, detail="Only the holder may decide this request")
    if req.status != "pending":
        raise HTTPException(status_code=409, detail="Request already decided")
    return req


@router.post("/{request_id}/approve", response_model=CredentialAccessGrantOut)
def approve_credential_access(
    request_id: str,
    body: CredentialAccessDecision,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Holder approves: grant is purpose + claims + expiry bound."""
    req = _grant_for_request(db, request_id, current)
    req.status = "approved"
    req.decided_at = datetime.utcnow()
    req.decided_by = current.id

    grant = CredentialAccessGrant(
        credential_id=req.credential_id,
        requester_id=req.requester_id,
        purpose=req.purpose,
        allowed_claims=req.requested_claims,
        expires_at=datetime.utcnow() + timedelta(minutes=body.duration_minutes),
    )
    db.add(grant)
    db.flush()
    # Notify the requester their grant is live.
    db.add(
        Notification(
            user_id=req.requester_id,
            type="access_approved",
            title="Access granted",
            body=f"Your request for '{req.purpose}' was approved.",
            link="/access",
        )
    )
    audit_trail.record(
        db, current.id, "credential_access_granted", "credential", req.credential_id,
        metadata={"purpose": req.purpose, "claims": req.requested_claims, "grant": grant.id},
    )
    db.commit()
    db.refresh(grant)
    return _grant_out(grant)


@router.post("/{request_id}/deny")
def deny_credential_access(
    request_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req = _grant_for_request(db, request_id, current)
    req.status = "denied"
    req.decided_at = datetime.utcnow()
    req.decided_by = current.id
    db.add(
        Notification(
            user_id=req.requester_id,
            type="access_denied",
            title="Access request denied",
            body=f"Your request for '{req.purpose}' was denied by the holder.",
            link="/access",
        )
    )
    audit_trail.record(
        db, current.id, "credential_access_denied", "credential", req.credential_id,
        result="denied", metadata={"purpose": req.purpose},
    )
    db.commit()
    return {"id": req.id, "status": "denied"}


@router.post("/grants/{grant_id}/revoke")
def revoke_credential_grant(
    grant_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Instant revocation by the holder (or the requester)."""
    grant = db.get(CredentialAccessGrant, grant_id)
    if not grant:
        raise HTTPException(status_code=404, detail="Grant not found")
    cred = db.get(Credential, grant.credential_id)
    is_holder = cred is not None and cred.holder_id == current.id
    is_requester = grant.requester_id == current.id
    if not (is_holder or is_requester or current.role == "admin"):
        raise HTTPException(status_code=403, detail="Not permitted to revoke this grant")
    grant.status = "revoked"
    grant.revoked_at = datetime.utcnow()
    grant.revoked_by = current.id
    audit_trail.record(
        db, current.id, "credential_access_revoked", "credential", grant.credential_id,
        metadata={"grant": grant.id},
    )
    db.commit()
    return {"id": grant.id, "status": "revoked"}


@router.get("/content/{credential_id}", response_model=CredentialContentOut)
def read_granted_content(
    credential_id: str,
    purpose: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Server-enforced read of permitted claims for an active, purpose-matching grant."""
    now = datetime.utcnow()
    grant = (
        db.query(CredentialAccessGrant)
        .filter(
            CredentialAccessGrant.credential_id == credential_id,
            CredentialAccessGrant.requester_id == current.id,
            CredentialAccessGrant.status == "active",
        )
        .first()
    )
    if not grant:
        audit_trail.record(
            db, current.id, "credential_content_denied", "credential", credential_id,
            result="denied", metadata={"reason": "no_grant", "purpose": purpose},
        )
        db.commit()
        raise HTTPException(status_code=403, detail="No active grant for this credential")
    if grant.purpose.lower() != purpose.strip().lower():
        audit_trail.record(
            db, current.id, "credential_content_denied", "credential", credential_id,
            result="denied", metadata={"reason": "purpose_mismatch", "purpose": purpose},
        )
        db.commit()
        raise HTTPException(status_code=403, detail="Purpose does not match the grant scope")
    if grant.expires_at < now:
        grant.status = "expired"
        audit_trail.record(
            db, current.id, "credential_content_denied", "credential", credential_id,
            result="denied", metadata={"reason": "expired"},
        )
        db.commit()
        raise HTTPException(status_code=403, detail="Grant has expired")

    credential = db.get(Credential, credential_id)
    if not credential or credential.status != "active":
        raise HTTPException(status_code=403, detail="Credential is not active")

    allowed = set(grant.allowed_claims)
    claims = {c.claim_key: c.claim_value for c in credential.claims if c.claim_key in allowed}
    audit_trail.record(
        db, current.id, "credential_content_allowed", "credential", credential_id,
        metadata={"purpose": purpose, "grant": grant.id, "claim_count": len(claims)},
    )
    db.commit()
    return CredentialContentOut(
        credential_id=credential.id,
        holder_did=credential.holder.did,
        type=credential.type,
        issued_at=credential.issued_at,
        purpose=grant.purpose,
        claims=claims,
        granted_until=grant.expires_at,
    )


def _req_out(r: CredentialAccessRequest) -> CredentialAccessRequestOut:
    return CredentialAccessRequestOut(
        id=r.id,
        credential_id=r.credential_id,
        requester_id=r.requester_id,
        purpose=r.purpose,
        requested_claims=r.requested_claims,
        status=r.status,
        expires_at=r.expires_at,
        created_at=r.created_at,
        decided_at=r.decided_at,
    )


def _grant_out(g: CredentialAccessGrant) -> CredentialAccessGrantOut:
    return CredentialAccessGrantOut(
        id=g.id,
        credential_id=g.credential_id,
        requester_id=g.requester_id,
        purpose=g.purpose,
        allowed_claims=g.allowed_claims,
        status=g.status,
        granted_at=g.granted_at,
        expires_at=g.expires_at,
        revoked_at=g.revoked_at,
    )