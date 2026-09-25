import base64
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
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
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    decode_password_reset_token,
    hash_password,
    verify_password,
)
from app.core.sessions import create_session, revoke_session, revoke_sessions_for_user
from app.core.webauthn_challenges import challenge_store
from app.db.session import SessionLocal, get_db
from app.models import Notification, TrustedDevice, User, WebAuthnCredential
from app.schemas import (
    DeviceRegisterRequest,
    LoginStartRequest,
    PasskeyCompleteRequest,
    PasswordChangeRequest,
    PasswordLoginRequest,
    PasswordRegisterRequest,
    PasswordResetCompleteRequest,
    PasswordResetRequest,
    RegisterStartRequest,
    TokenResponse,
    TrustedDeviceOut,
)
from app.services import audit_trail

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
log = logging.getLogger("trustvault.auth")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _from_b64url(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


def _issue_session(
    db: Session,
    user: User,
    jti: str | None = None,
    ip_addr: str | None = None,
    user_agent: str | None = None,
) -> TokenResponse:
    jti = jti or str(uuid.uuid4())
    token = create_access_token(subject=user.id, extra={"role": user.role, "jti": jti})
    create_session(db, user, jti, ip_addr=ip_addr, user_agent=user_agent)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "did": user.did,
            "role": user.role,
            "status": user.status,
        },
    )


# ------------------------- Password registration + login -------------------------


@router.post("/register", response_model=TokenResponse)
def register(
    body: PasswordRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Real account creation (password). Users may never self-register as admin."""
    email = body.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="User already registered")

    user = User(
        email=email,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        role="holder",  # issuer/verifier roles are granted after org verification
        did=f"did:trustvault:{uuid.uuid4()}",
    )
    db.add(user)
    db.flush()
    audit_trail.record(db, user.id, "user_registered", "user", user.id, metadata={"method": "password"})
    ip, ua = _client_meta(request)
    response = _issue_session(db, user, ip_addr=ip, user_agent=ua)
    db.commit()
    return response


@router.post("/login", response_model=TokenResponse)
def login_password(
    body: PasswordLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate with email + password, mint a DB-backed session."""
    email = body.email.lower()
    user = db.query(User).filter(User.email == email).first()
    ip, ua = _client_meta(request)
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        audit_trail.record(
            db, user.id if user else None, "login_failed", "user", user.id if user else None,
            result="denied", reason="invalid credentials", metadata={"method": "password", "ip": ip},
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="Account is not active")
    response = _issue_session(db, user, ip_addr=ip, user_agent=ua)
    audit_trail.record(db, user.id, "login_success", "user", user.id, metadata={"method": "password", "ip": ip})
    db.commit()
    return response


# ------------------------- Passkey registration ceremony -------------------------


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


@router.post("/register/complete", response_model=TokenResponse)
def register_complete(
    body: PasskeyCompleteRequest,
    request: Request,
    db: Session = Depends(get_db),
):
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

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="User already registered")
    user = User(
        email=email,
        did=f"did:trustvault:{uuid.uuid4()}",
        role=pending.role if pending.role != "admin" else "holder",
    )
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
    db.flush()
    audit_trail.record(db, user.id, "user_registered", "user", user.id, metadata={"method": "passkey"})
    ip, ua = _client_meta(request)
    response = _issue_session(db, user, ip_addr=ip, user_agent=ua)
    db.commit()
    return response


# ------------------------- Passkey login ceremony -------------------------


@router.post("/login/start")
def login_start(body: LoginStartRequest):
    """Step 1/2 of passkey login: return WebAuthn assertion options."""
    email = body.email.lower()
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user or user.status != "active":
            raise HTTPException(status_code=404, detail="User not found or inactive")
        creds = db.query(WebAuthnCredential).filter(WebAuthnCredential.user_id == user.id).all()
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


@router.post("/login/complete", response_model=TokenResponse)
def login_complete(
    body: PasskeyCompleteRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Step 2/2: verify assertion, upsert device, issue DB-backed session."""
    email = body.email.lower()
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
        audit_trail.record(
            db, user.id, "login_failed", "user", user.id,
            result="denied", reason="passkey assertion failed", metadata={"method": "passkey"},
        )
        db.commit()
        raise HTTPException(status_code=400, detail=f"Passkey verification failed: {exc}") from exc

    stored_cred.sign_count = verification.new_sign_count

    device = (
        db.query(TrustedDevice)
        .filter(TrustedDevice.user_id == user.id, TrustedDevice.device_key_id == stored_cred.credential_id)
        .first()
    )
    if device:
        device.last_seen = datetime.utcnow()
        device.status = "trusted"
    else:
        known = db.query(TrustedDevice).filter(TrustedDevice.user_id == user.id).count()
        db.add(
            TrustedDevice(
                user_id=user.id,
                device_key_id=stored_cred.credential_id,
                label=body.label or "unknown",
                status="trusted" if known == 0 else "unknown",
            )
        )
    ip, ua = _client_meta(request)
    response = _issue_session(db, user, ip_addr=ip, user_agent=ua)
    audit_trail.record(db, user.id, "login_success", "user", user.id, metadata={"method": "passkey", "ip": ip})
    db.commit()
    return response


# ------------------------- Session + password management -------------------------


@router.get("/users")
def list_users(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lightweight directory of active users (for consent flows / org management)."""
    rows = db.query(User).filter(User.status == "active").all()
    return [
        {"id": u.id, "email": u.email, "did": u.did, "role": u.role, "full_name": u.full_name}
        for u in sorted(rows, key=lambda x: x.email)
    ]


@router.get("/me")
def me(current: User = Depends(get_current_user)):
    return {
        "id": current.id,
        "email": current.email,
        "full_name": current.full_name,
        "did": current.did,
        "role": current.role,
        "status": current.status,
        "organization_id": current.organization_id,
    }


@router.post("/change-password")
def change_password(
    body: PasswordChangeRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current.password_hash or not verify_password(body.old_password, current.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    current.password_hash = hash_password(body.new_password)
    audit_trail.record(db, current.id, "password_changed", "user", current.id)
    db.commit()
    return {"ok": True}


@router.post("/password-reset/request")
def request_password_reset(
    body: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    """Create a real reset token. Delivery is email in production; the MVP
    surfaces it to the authenticated account as a notification and, when
    `reset_token_dev_delivery` is enabled, returns it for the demo/e2e flow."""
    email = body.email.lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Same response whether or not the account exists (no user enumeration).
        return {"ok": True, "reset_token": None}

    token, expires_at = create_password_reset_token(email)
    db.add(
        Notification(
            user_id=user.id,
            type="password_reset",
            title="Password reset initiated",
            body="A password reset was requested. Complete it with the reset link.",
            link=f"/#/reset?token={token}",
        )
    )
    audit_trail.record(db, user.id, "password_reset_requested", "user", user.id)
    db.commit()
    if settings.reset_token_dev_delivery:
        return {"ok": True, "reset_token": token}
    return {"ok": True, "reset_token": None}


@router.post("/password-reset/complete")
def complete_password_reset(
    body: PasswordResetCompleteRequest,
    db: Session = Depends(get_db),
):
    email = decode_password_reset_token(body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Reset token is invalid or expired")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(body.new_password)
    revoked = revoke_sessions_for_user(db, user.id, revoked_by=user.id)
    audit_trail.record(db, user.id, "password_reset_completed", "user", user.id, metadata={"sessions_revoked": revoked})
    db.commit()
    return {"ok": True}


@router.post("/logout")
def logout(
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke this session server-side (not just drop the token)."""
    jti = _current_jti(request)
    if jti:
        revoke_session(db, jti, revoked_by=current.id)
        audit_trail.record(db, current.id, "logout", "session", jti)
        db.commit()
    return {"ok": True}


def _current_jti(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    payload = None
    from app.core.security import decode_access_token

    payload = decode_access_token(auth.split(" ", 1)[1])
    return payload.get("jti") if payload else None


# ------------------------- Trusted devices -------------------------


@router.get("/devices", response_model=list[TrustedDeviceOut])
def list_devices(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return [
        TrustedDeviceOut(
            id=d.id,
            label=d.label,
            browser=d.browser,
            os=d.os,
            first_seen=d.first_seen,
            last_seen=d.last_seen,
            status=d.status,
        )
        for d in db.query(TrustedDevice)
        .filter(TrustedDevice.user_id == current.id)
        .order_by(TrustedDevice.last_seen.desc())
        .all()
    ]


@router.post("/devices")
def register_device(
    body: DeviceRegisterRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = TrustedDevice(
        user_id=current.id,
        device_key_id=f"manual-{uuid.uuid4()}",
        label=body.label or "manual",
        status="unknown",
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return {"id": device.id, "label": device.label, "status": device.status}


@router.delete("/devices/{device_id}")
def remove_device(
    device_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = db.get(TrustedDevice, device_id)
    if not device or device.user_id != current.id:
        raise HTTPException(status_code=404, detail="Device not found")
    device.status = "revoked"
    audit_trail.record(db, current.id, "device_revoked", "trusted_device", device_id)
    db.commit()
    return {"id": device_id, "status": "revoked"}