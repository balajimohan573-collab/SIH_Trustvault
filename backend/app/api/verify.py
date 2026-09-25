"""Public credential verification (the verifier-facing flow).

`GET /verify/{token}` accepts either:
  * the credential's opaque API token (long-lived, holder-controlled), or
  * a short-lived QR JWT emitted by the holder's app.

Seven checks run every time; the outcome is VERIFIED / INVALID / EXPIRED /
REVOKED and every call is recorded to verification_events.
"""
import hashlib
import io
import json
import logging
from datetime import datetime, timezone

import qrcode
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.qr_tokens import verify_qr_token
from app.db.session import get_db
from app.models import Credential, Organization, VerificationEvent
from app.schemas import PublicVerifyResponse

router = APIRouter(prefix="/verify", tags=["verify"])
settings = get_settings()
log = logging.getLogger("trustvault.verify")

QR_SCOPE = "credential_verify"


def _verify(db: Session, token: str) -> tuple[PublicVerifyResponse, Credential | None]:
    checks: dict[str, bool] = {}
    reason: str | None = None
    purpose: str | None = None
    credential: Credential | None = None

    # Check 1: the token itself parses.
    payload = verify_qr_token(token)
    api_cred = db.query(Credential).filter(Credential.api_verification_token == token).first()
    credential = api_cred
    if payload:
        purpose = payload.get("purpose")
        found = db.get(Credential, payload.get("sub"))
        credential = found or credential
    checks["token_valid"] = payload is not None or api_cred is not None
    if not checks["token_valid"]:
        return _failed("INVALID", "invalid_token", checks, reason="The verification token is missing, malformed, or expired."), None

    if credential is None:
        return _failed("INVALID", "unknown", checks, reason="No credential matches this token."), None

    # Check 2: credential exists (guaranteed by _verify above).
    checks["credential_exists"] = True

    # Check 3: not revoked.
    checks["not_revoked"] = credential.status != "revoked"
    # Check 4: not suspended.
    checks["not_suspended"] = credential.status != "suspended"
    # Check 5: not expired.
    expires_past = False
    if credential.expiry_date:
        try:
            expires_past = datetime.strptime(credential.expiry_date, "%Y-%m-%d").date() < datetime.now(timezone.utc).date()
        except ValueError:
            expires_past = False
    checks["not_expired"] = not expires_past
    # Check 6: claims integrity (canonical hash matches the stored record).
    canonical = {c.claim_key: c.claim_value for c in credential.claims}
    recomputed = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    checks["claims_integrity"] = recomputed == credential.claims_hash
    # Check 7: status consistent with the above.
    checks["status_active"] = credential.status == "active"

    result = "VERIFIED"
    if not checks["claims_integrity"]:
        result = "INVALID"
        reason = "Credential data failed its integrity check."
    elif checks["not_revoked"] and checks["not_suspended"] and checks["not_expired"] and checks["status_active"]:
        result = "VERIFIED"
        reason = None
    elif not checks["not_revoked"]:
        result = "REVOKED"
        reason = "This credential has been revoked."
    elif not checks["not_expired"]:
        result = "EXPIRED"
        reason = "This credential has expired."
    else:
        result = "REVOKED" if not checks["status_active"] else "INVALID"
        reason = reason or "This credential is not currently active."

    holder = credential.holder
    org = db.get(Organization, credential.issuer_org_id)
    public_claims = {c.claim_key: c.claim_value for c in credential.claims if c.public}

    _record(db, credential, token, result, checks, purpose)
    return _build(credential, result, checks, holder.did if holder else None, org.name if org else None, public_claims, purpose, reason), credential


def _record(db: Session, credential: Credential, token: str, result: str, checks: dict, purpose: str | None) -> None:
    db.add(
        VerificationEvent(
            credential_id=credential.id,
            verification_token=token[:128],
            result=result,
            checks=checks,
        )
    )
    db.commit()
    log.info("Verification of %s -> %s (purpose=%s)", credential.id, result, purpose)


def _build(credential: Credential, result: str, checks: dict, holder_did, org_name, public_claims, purpose, reason) -> PublicVerifyResponse:
    return PublicVerifyResponse(
        valid=result == "VERIFIED",
        result=result,
        status=credential.status,
        credential_id=credential.id,
        holder_did=holder_did,
        holder_name=credential.holder.full_name,
        type=credential.type,
        issuer_org=org_name,
        issued_at=credential.issued_at,
        expiry_date=credential.expiry_date,
        public_claims=public_claims,
        checks=checks,
        reason=reason,
        purpose=purpose,
    )


def _failed(result: str, status: str, checks: dict, reason: str) -> PublicVerifyResponse:
    return PublicVerifyResponse(
        valid=False,
        result=result,
        status=status,
        checks=checks,
        reason=reason,
    )


@router.get("/{token}", response_model=PublicVerifyResponse)
def verify_token(token: str, db: Session = Depends(get_db)):
    """Public endpoint — no auth required by design. Returns the full audit of checks."""
    response, _ = _verify(db, token)
    return response


@router.get("/{token}/qr")
def verify_qr_image(token: str, db: Session = Depends(get_db)):
    """Render the verification URL as a QR PNG (server-side, no client library)."""
    response, _ = _verify(db, token)
    url = f"{settings.verification_base_url}/#/verify-result?token={token}"
    img = qrcode.make(url)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(
        buf.getvalue(),
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="verify-{token[:8]}.png"'},
    )