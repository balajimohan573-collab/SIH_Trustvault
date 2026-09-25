import hashlib
import json
import logging
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.crypto import sha256_hex
from app.core.qr_tokens import create_qr_token, verify_qr_token
from app.db.session import get_db
from app.models import (
    Credential,
    CredentialClaim,
    CredentialFile,
    CredentialIssuer,
    CredentialAccessGrant,
    Organization,
    Revocation,
    User,
)
from app.schemas import (
    CredentialFileOut,
    CredentialIssueRequest,
    CredentialResponse,
    QrGenerateRequest,
    QrGenerateResponse,
    QrVerifyRequest,
    QrVerifyResponse,
    RevokeRequest,
    SuspendRequest,
    VerifyResponse,
)
from app.services import audit, audit_trail
from app.services.file_validation import FileValidationError, validate_upload
from app.services.storage import backend

router = APIRouter(prefix="/credentials", tags=["credentials"])
log = logging.getLogger("trustvault.credentials")


def _claims_hash(claims: list[dict]) -> str:
    canonical = {c["key"]: c["value"] for c in claims}
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return sha256_hex(blob)


def _issuance_allowed(db: Session, user: User) -> Organization:
    """Only a member of a VERIFIED organization (or admin) may issue."""
    if user.role == "admin":
        return None
    if user.role != "issuer":
        raise HTTPException(status_code=403, detail="Only verified issuers may issue credentials")
    org = db.get(Organization, user.organization_id) if user.organization_id else None
    if org is None or org.verification_status != "verified":
        raise HTTPException(
            status_code=403,
            detail="You must belong to a VERIFIED organization to issue credentials. Apply and get it approved.",
        )
    return org


@router.post("/issue", response_model=CredentialResponse)
@router.post("", response_model=CredentialResponse)
def issue_credential(
    body: CredentialIssueRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Real issuance: only a member of a verified org (or admin) can issue."""
    org = _issuance_allowed(db, current)

    holder = None
    if body.holder_email:
        holder = db.query(User).filter(User.email == body.holder_email.lower()).first()
        if holder is None:
            raise HTTPException(status_code=404, detail="Holder not found")
    if holder is None:
        holder = current

    if not body.claims:
        raise HTTPException(status_code=400, detail="A credential needs at least one structured claim")

    token = secrets.token_urlsafe(32)
    claims_hash = _claims_hash([c.model_dump() for c in body.claims])
    now = datetime.utcnow()

    credential = Credential(
        api_verification_token=token,
        holder_id=holder.id,
        issuer_org_id=org.id if org else _admin_org_id(db, current),
        issuer_user_id=current.id,
        type=body.type,
        title=body.title,
        external_id=body.external_id,
        issuer_name=(org.name if org else current.full_name or current.email),
        claims_hash=claims_hash,
        hash=sha256_hex(token.encode()),
        status="active",
        issue_date=body.issue_date or now.strftime("%Y-%m-%d"),
        expiry_date=body.expiry_date,
    )
    db.add(credential)
    db.flush()
    for cl in body.claims:
        db.add(
            CredentialClaim(
                credential_id=credential.id,
                claim_key=cl.key,
                claim_value=cl.value,
                claim_type=cl.claim_type,
                public=cl.public,
            )
        )
    db.add(
        CredentialIssuer(
            credential_id=credential.id,
            organization_id=credential.issuer_org_id,
            issuer_user_id=current.id,
        )
    )
    audit_trail.record(
        db, current.id, "credential_issued", "credential", credential.id,
        metadata={"holder": holder.id, "type": body.type},
    )
    db.flush()
    # Queue a best-effort on-chain anchor proof; "pending" until a real tx exists.
    if audit.anchor(db, event_type="credential_issued", user_id=current.id, risk=None):
        credential.anchor_tx_hash = "pending"
    db.commit()
    db.refresh(credential)
    log.info("Credential %s issued by %s (org %s) to %s", credential.id, current.id, credential.issuer_org_id, holder.id)
    return _to_response(credential)


def _admin_org_id(db: Session, admin: User) -> str:
    """Admin bootstrap fallback: create the platform's own verified org once."""
    org = db.query(Organization).filter(Organization.official_domain == "trustvault.local").first()
    if org is None:
        org = Organization(
            name="TrustVault Platform",
            official_domain="trustvault.local",
            org_identifier="platform",
            verification_status="verified",
            verified_by=admin.id,
            verified_at=datetime.utcnow(),
            created_by=admin.id,
        )
        db.add(org)
        db.flush()
    return org.id


@router.get("", response_model=list[CredentialResponse])
def list_credentials(
    holder: str | None = None,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List credentials the user holds, plus (for issuers/admins) what they issued.
    `holder=<user_id>` is admin/issuer-only."""
    q = db.query(Credential)
    if holder is None or holder == "me":
        q = q.filter(
            (Credential.holder_id == current.id) | (Credential.issuer_user_id == current.id)
        )
    else:
        if current.role not in ("issuer", "admin"):
            raise HTTPException(status_code=403, detail="Only issuers may browse holders' credentials")
        q = q.filter(Credential.holder_id == holder)
    return [_to_response(c) for c in q.order_by(Credential.issued_at.desc()).all()]


def _can_see(db: Session, credential: Credential, user: User) -> bool:
    if user.role == "admin":
        return True
    if credential.holder_id == user.id or credential.issuer_user_id == user.id:
        return True
    grant = (
        db.query(CredentialAccessGrant)
        .filter(
            CredentialAccessGrant.credential_id == credential.id,
            CredentialAccessGrant.requester_id == user.id,
            CredentialAccessGrant.status == "active",
        )
        .first()
    )
    return grant is not None and grant.expires_at > datetime.utcnow()


@router.get("/{credential_id}", response_model=CredentialResponse)
def get_credential_by_id(
    credential_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    credential = db.get(Credential, credential_id)
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    if not _can_see(db, credential, current):
        raise HTTPException(status_code=403, detail="Forbidden")
    return _to_response(credential)


@router.get("/{credential_id}/verify", response_model=VerifyResponse)
def verify_credential(
    credential_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Status check (the verifier flow). Full public verification lives in /verify."""
    credential = db.get(Credential, credential_id)
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    return VerifyResponse(
        id=credential.id,
        valid=credential.status == "active",
        status=credential.status,
        hash_match=True,
        purpose=None,
    )


# ------------------------- Evidence files -------------------------


@router.post("/{credential_id}/files", response_model=CredentialFileOut)
async def upload_evidence(
    credential_id: str,
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a supporting evidence document (PDF/PNG/JPG). Stored encrypted."""
    credential = db.get(Credential, credential_id)
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    if credential.holder_id != current.id and credential.issuer_user_id != current.id and current.role != "admin":
        raise HTTPException(status_code=403, detail="Only the holder or issuing party may attach evidence")

    data = await file.read()
    try:
        meta = validate_upload(data, file.filename, file.content_type)
    except FileValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    aad = credential.id.encode()
    obj = backend.save(data, aad=aad)
    existing_primary = (
        db.query(CredentialFile)
        .filter(CredentialFile.credential_id == credential.id, CredentialFile.is_primary.is_(True))
        .first()
    )
    row = CredentialFile(
        credential_id=credential.id,
        original_filename=meta["original_filename"],
        storage_uri=obj.storage_uri,
        sha256=obj.sha256,
        byte_size=obj.byte_size,
        content_type=meta["content_type"],
        detected_type=meta["detected_type"],
        is_primary=existing_primary is None,
        uploaded_by=current.id,
    )
    db.add(row)
    db.flush()
    audit_trail.record(
        db, current.id, "credential_evidence_uploaded", "credential_file", row.id,
        metadata={"credential_id": credential.id, "sha256": obj.sha256, "size": obj.byte_size},
    )
    db.commit()
    db.refresh(row)
    return CredentialFileOut(
        id=row.id,
        original_filename=row.original_filename,
        sha256=row.sha256,
        byte_size=row.byte_size,
        content_type=row.content_type,
        detected_type=row.detected_type,
        is_primary=row.is_primary,
    )


@router.get("/{credential_id}/file/{file_id}")
def download_evidence(
    credential_id: str,
    file_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download the decrypted evidence (holder, issuer, admin or active grantee)."""
    credential = db.get(Credential, credential_id)
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    if not _can_see(db, credential, current):
        raise HTTPException(status_code=403, detail="Forbidden")
    row = db.get(CredentialFile, file_id)
    if not row or row.credential_id != credential_id:
        raise HTTPException(status_code=404, detail="File not found")
    plaintext = backend.load(row.storage_uri, expected_sha256=row.sha256, aad=credential.id.encode())
    return Response(
        content=plaintext,
        media_type=row.content_type,
        headers={"Content-Disposition": f'attachment; filename="{row.original_filename}"'},
    )


# ------------------------- Lifecycle: suspend / resume / revoke -------------------------


@router.post("/{credential_id}/suspend")
def suspend_credential(
    credential_id: str,
    body: SuspendRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    credential = db.get(Credential, credential_id)
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    if credential.issuer_user_id != current.id and current.role != "admin":
        raise HTTPException(status_code=403, detail="Only the issuer may suspend a credential")
    if credential.status == "revoked":
        raise HTTPException(status_code=409, detail="Revoked credentials cannot be suspended")
    credential.status = "suspended"
    credential.suspended_at = datetime.utcnow()
    audit_trail.record(
        db, current.id, "credential_suspended", "credential", credential.id,
        result="success", reason=body.reason,
    )
    db.commit()
    return {"id": credential.id, "status": "suspended", "suspended_at": credential.suspended_at.isoformat()}


@router.post("/{credential_id}/resume")
def resume_credential(
    credential_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    credential = db.get(Credential, credential_id)
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    if credential.issuer_user_id != current.id and current.role != "admin":
        raise HTTPException(status_code=403, detail="Only the issuer may reactivate a credential")
    if credential.status == "revoked":
        raise HTTPException(status_code=409, detail="Revoked credentials cannot be reactivated")
    credential.status = "active"
    credential.suspended_at = None
    audit_trail.record(db, current.id, "credential_resumed", "credential", credential.id)
    db.commit()
    return {"id": credential.id, "status": "active"}


@router.post("/{credential_id}/revoke")
def revoke_credential(
    credential_id: str,
    body: RevokeRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    credential = db.get(Credential, credential_id)
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    if (
        credential.holder_id != current.id
        and credential.issuer_user_id != current.id
        and current.role != "admin"
    ):
        raise HTTPException(status_code=403, detail="Only the holder, issuer, or admin may revoke")
    if credential.status == "revoked":
        raise HTTPException(status_code=409, detail="Credential already revoked")

    credential.status = "revoked"
    credential.revoked_at = datetime.utcnow()
    revoke_type = "issuer" if credential.issuer_user_id == current.id else ("admin" if current.role == "admin" else "holder")
    rev = Revocation(
        credential_id=credential.id,
        revoked_by=current.id,
        revoke_type=revoke_type,
        reason=body.reason,
    )
    db.add(rev)
    db.flush()
    audit_trail.record(
        db, current.id, "credential_revoked", "credential", credential.id,
        result="success", reason=body.reason,
    )
    # Revoke outstanding grants immediately.
    now = datetime.utcnow()
    grants = (
        db.query(CredentialAccessGrant)
        .filter(CredentialAccessGrant.credential_id == credential.id, CredentialAccessGrant.status == "active")
        .all()
    )
    for g in grants:
        g.status = "revoked"
        g.revoked_at = now
        g.revoked_by = current.id
    if audit.anchor(db, event_type="credential_revoked", user_id=current.id, risk=None):
        rev.anchor_tx_hash = "pending"
    db.commit()
    db.refresh(credential)
    log.warning("Credential %s revoked by %s (%s)", credential.id, current.id, body.reason)
    return {
        "id": credential.id,
        "status": "revoked",
        "revoked_at": credential.revoked_at.isoformat(),
        "grants_revoked": len(grants),
    }


# ------------------------- QR -------------------------


@router.post("/qr/generate", response_model=QrGenerateResponse)
def generate_qr(
    body: QrGenerateRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Emit a short-lived signed QR token bound to a credential + purpose."""
    credential = db.get(Credential, body.credential_id)
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    if credential.holder_id != current.id and credential.issuer_user_id != current.id and current.role != "admin":
        raise HTTPException(status_code=403, detail="Only the holder or issuer may generate a QR")

    qr_token, expires_at = create_qr_token(credential.id, body.purpose, body.expires_minutes)
    log.info("QR token for credential %s generated by %s (purpose=%s)", credential.id, current.id, body.purpose)
    return QrGenerateResponse(
        qr_token=qr_token,
        qr_url=f"/#/verify?token={qr_token}",
        expires_at=expires_at,
    )


@router.post("/qr/verify", response_model=QrVerifyResponse)
def verify_qr(body: QrVerifyRequest, db: Session = Depends(get_db)):
    """Public QR verification (kept for the in-app verifier flow)."""
    payload = verify_qr_token(body.qr_token)
    if not payload:
        return QrVerifyResponse(
            id="",
            valid=False,
            status="invalid_token",
            hash_match=False,
            purpose=None,
            explanation="QR token is missing, tampered, or expired. Ask the holder to refresh it.",
        )
    credential = db.get(Credential, payload.get("sub"))
    if not credential:
        return QrVerifyResponse(
            id=str(payload.get("sub", "")),
            valid=False,
            status="unknown",
            hash_match=False,
            purpose=payload.get("purpose"),
            explanation="Credential does not exist in the registry.",
        )
    holder = db.get(User, credential.holder_id)
    valid = credential.status == "active"
    exp = payload.get("exp")
    return QrVerifyResponse(
        id=credential.id,
        valid=valid,
        status=credential.status,
        hash_match=True,
        holder_did=holder.did if holder else None,
        type=credential.type,
        issuer_id=credential.issuer_user_id,
        issued_at=credential.issued_at,
        purpose=payload.get("purpose"),
        expires_at=datetime.fromtimestamp(exp) if exp else None,
        selective_disclosure_ready=True,
        explanation=(
            "Credential is ACTIVE and the QR signature is valid."
            if valid
            else "Credential has been revoked or invalidated."
        ),
    )


def _to_response(c: Credential) -> CredentialResponse:
    return CredentialResponse(
        id=c.id,
        type=c.type,
        title=c.title,
        issuer_name=c.issuer_name,
        issuer_org_id=c.issuer_org_id,
        issuer_user_id=c.issuer_user_id,
        holder_id=c.holder_id,
        status=c.status,
        issue_date=c.issue_date,
        expiry_date=c.expiry_date,
        external_id=c.external_id,
        claims_hash=c.claims_hash,
        hash=c.hash,
        anchor_tx_hash=c.anchor_tx_hash,
        issued_at=c.issued_at,
        revoked_at=c.revoked_at,
        suspended_at=c.suspended_at,
        claims=[
            {"key": cl.claim_key, "value": cl.claim_value, "claim_type": cl.claim_type, "public": cl.public}
            for cl in c.claims
        ],
        files=[
            CredentialFileOut(
                id=f.id,
                original_filename=f.original_filename,
                sha256=f.sha256,
                byte_size=f.byte_size,
                content_type=f.content_type,
                detected_type=f.detected_type,
                is_primary=f.is_primary,
            )
            for f in c.files
        ],
    )