import base64
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.options_to_json import options_to_json
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token
from app.core.sessions import session_store
from app.core.webauthn_challenges import challenge_store
from app.db.session import SessionLocal, get_db
from app.models import Device, User, WebAuthnCredential
from app.schemas import (
    DeviceRegisterRequest,
    LoginStartRequest,
    PasskeyCompleteRequest,
    RegisterStartRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
log = logging.getLogger("trustvault.auth")


@router.get("/users")
def list_users(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lightweight directory of active users (for NFT transfers, consent flows)."""
    rows = db.query(User).filter(User.status == "active").all()
    return [
        {"id": u.id, "email": u.email, "did": u.did, "role": u.role}
        for u in sorted(rows, key=lambda x: x.email)
    ]


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _from_b64url(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _serialize_token(user: User) -> TokenResponse:
    jti = str(uuid.uuid4())
    token = create_access_token(subject=user.id, extra={"role": user.role, "jti": jti})
    session_store.put(jti, {"user_id": user.id, "role": user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user={
            "id": user.id,
            "email": user.email,
            "did": user.did,
            "role": user.role,
            "status": user.status,
        },
    )


# ------------------------- Registration ceremony -------------------------


@router.post("/register/start")
def register_start(body: RegisterStartRequest):
    """Step 1/2 of passkey registration: return WebAuthn creation options."""
    email = body.email.lower()
    user_handle = uuid.uuid5(uuid.NAMESPACE_URL, f"trustvault:{email}").bytes

    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=user_handle,
        user_name=email,
        user_display_name=email.split("@")[0],
        attestation=AttestationConveyancePreference.DIRECT,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    challenge_store.new_registration(email, body.role, options.challenge)
    return {"options": options_to_json(options)}


@router.post("/register/complete")
def register_complete(body: PasskeyCompleteRequest):
    """Step 2/2: verify attestation, create the user + passkey credential."""
    email = body.email.lower()
    pending = challenge_store.take_registration(email)
    if pending is None:
        raise HTTPException(status_code=400, detail="No pending registration challenge")

    try:
        verification = verify_registration_response(
            credential=body.credential,
            expected_challenge=pending.challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
        )
    except InvalidRegistrationResponse as exc:
        log.warning("Registration verification failed for %s: %s", email, exc)
        raise HTTPException(status_code=400, detail=f"Passkey verification failed: {exc}") from exc

    with SessionLocal() as db:
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=409, detail="User already registered")
        user = User(email=email, did=f"did:trustvault:{uuid.uuid4()}", role=pending.role)
        db.add(user)
        db.flush()
        db.add(
            WebAuthnCredential(
                user_id=user.id,
                credential_id=_b64url(verification.credential_id),
                public_key=_b64url(verification.credential_public_key),
                sign_count=verification.sign_count,
            )
        )
        db.commit()
        db.refresh(user)

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "did": user.did,
            "role": user.role,
            "status": user.status,
        }
    }


# ------------------------- Login ceremony -------------------------


@router.post("/login/start")
def login_start(body: LoginStartRequest):
    """Step 1/2 of passkey login: return WebAuthn assertion options."""
    email = body.email.lower()
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user or user.status != "active":
            raise HTTPException(status_code=404, detail="User not found or inactive")
        creds = (
            db.query(WebAuthnCredential).filter(WebAuthnCredential.user_id == user.id).all()
        )
        if not creds:
            raise HTTPException(status_code=400, detail="No passkeys registered for this user")

    allow_credentials = [
        PublicKeyCredentialDescriptor(
            type="public-key",
            id=_from_b64url(c.credential_id),
            transports=[AuthenticatorTransport.INTERNAL, AuthenticatorTransport.USB],
        )
        for c in creds
    ]

    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        user_verification=UserVerificationRequirement.PREFERRED,
        allow_credentials=allow_credentials,
    )
    challenge_store.new_assertion(user.id, options.challenge)
    return {"options": options_to_json(options)}


@router.post("/login/complete")
def login_complete(body: PasskeyCompleteRequest):
    """Step 2/2: verify assertion, upsert device, issue JWT session."""
    email = body.email.lower()
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user or user.status != "active":
            raise HTTPException(status_code=404, detail="User not found or inactive")

        pending = challenge_store.take_assertion(user.id)
        if pending is None:
            raise HTTPException(status_code=400, detail="No pending login challenge")

        stored_cred = (
            db.query(WebAuthnCredential)
            .filter(WebAuthnCredential.user_id == user.id)
            .order_by(WebAuthnCredential.created_at.desc())
            .first()
        )
        if stored_cred is None:
            raise HTTPException(status_code=400, detail="No passkey credential stored")

        try:
            verification = verify_authentication_response(
                credential=body.credential,
                expected_challenge=pending.challenge,
                expected_rp_id=settings.webauthn_rp_id,
                expected_origin=settings.webauthn_origin,
                credential_public_key=_from_b64url(stored_cred.public_key),
                credential_current_sign_count=stored_cred.sign_count,
                require_user_verification=False,
            )
        except InvalidAuthenticationResponse as exc:
            log.warning("Assertion verification failed for %s: %s", email, exc)
            raise HTTPException(status_code=400, detail=f"Passkey verification failed: {exc}") from exc

        stored_cred.sign_count = verification.new_sign_count

        device = (
            db.query(Device)
            .filter(Device.user_id == user.id, Device.device_key_id == stored_cred.credential_id)
            .first()
        )
        if device:
            device.last_seen = datetime.utcnow()
            device.status = "active"
        else:
            known = db.query(Device).filter(Device.user_id == user.id).count()
            db.add(
                Device(
                    user_id=user.id,
                    device_key_id=stored_cred.credential_id,
                    label=body.label or "unknown",
                    status="active" if known == 0 else "new",
                )
            )
        db.commit()
        db.refresh(user)

    return _serialize_token(user)


# ------------------------- Dev-mode fallback login (no hardware passkey needed) -------------------------


@router.post("/login/dev")
def login_dev(body: LoginStartRequest):
    """DEMO ONLY.

    Issues a JWT for a seeded user without a WebAuthn ceremony. Used by the
    demo script, the automated tests, and the attack-simulation CLI so the
    security flow can be exercised without a physical authenticator.
    """
    email = body.email.lower()
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user or user.status != "active":
            raise HTTPException(status_code=404, detail="User not found or inactive")
        db.add(
            Device(
                user_id=user.id,
                device_key_id=f"dev-sim-{uuid.uuid4()}",
                label="dev-login",
                status="active",
            )
        )
        db.commit()
        db.refresh(user)
    return _serialize_token(user)


# ------------------------- Session helpers -------------------------


@router.get("/me")
def me(current: User = Depends(get_current_user)):
    return {
        "id": current.id,
        "email": current.email,
        "did": current.did,
        "role": current.role,
        "status": current.status,
    }


@router.post("/logout")
def logout(current: User = Depends(get_current_user)):
    return {"ok": True}


@router.post("/devices")
def register_device(
    body: DeviceRegisterRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = Device(
        user_id=current.id,
        device_key_id=f"manual-{uuid.uuid4()}",
        label=body.label or "manual",
        status="new",
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return {"id": device.id, "label": device.label, "status": device.status}