from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


# ---------- Auth ----------
class RegisterRequest(BaseModel):
    email: EmailStr
    role: str = Field(
        default="holder",
        pattern="^(holder|issuer|verifier|admin|manager|auditor|user)$",
    )


class LoginStartRequest(BaseModel):
    email: EmailStr


class RegisterStartRequest(BaseModel):
    email: EmailStr
    role: str = Field(
        default="holder",
        pattern="^(holder|issuer|verifier|admin|manager|auditor|user)$",
    )


class PasskeyCompleteRequest(BaseModel):
    email: EmailStr
    # WebAuthn client/authenticator response JSON
    credential: dict[str, Any]
    label: str = "default"


class DeviceRegisterRequest(BaseModel):
    label: str = "default"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


# ---------- Credentials ----------
class CredentialIssueRequest(BaseModel):
    holder_email: EmailStr
    type: str
    # Raw document bytes are hashed server-side during validation; payload may be a
    # base64 doc or a freeform claim object.
    document: dict[str, Any] = Field(default_factory=dict)
    document_base64: str | None = None


class CredentialResponse(BaseModel):
    id: str
    type: str
    hash: str
    status: str
    issuer_id: str
    holder_id: str
    issued_at: datetime
    revoked_at: datetime | None = None


class VerifyResponse(BaseModel):
    id: str
    valid: bool
    status: str
    hash_match: bool
    purpose: str | None = None


class RevokeRequest(BaseModel):
    reason: str | None = None


# ---------- Assets ----------
class AssetUploadResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    encrypted_uri: str
    file_hash: str
    cid: str | None = None
    content_type: str = "application/octet-stream"
    asset_class: str = "document"
    nft_token_id: str | None = None
    chain_tx_hash: str | None = None
    created_at: datetime


class AssetCreatePolicyRequest(BaseModel):
    requester_role: str
    purpose: str
    expires_at: datetime | None = None
    min_trust: int = Field(default=0, ge=0, le=100)
    # Policy-based location/time constraints (optional; users never enter GPS)
    location_scope: str | None = Field(default=None, max_length=255)
    location_strict: bool = Field(default=False)
    time_start: str | None = Field(default=None, description="HH:MM (local)")
    time_end: str | None = Field(default=None, description="HH:MM (local)")
    time_zone: str | None = Field(default=None, max_length=64)
    context_required: dict[str, Any] | None = Field(default=None)
    # Policy-based location/time constraints (optional; users never enter GPS)
    location_scope: str | None = Field(default=None, max_length=255)
    location_strict: bool = Field(default=False)
    time_start: str | None = Field(default=None, description="HH:MM (local)")
    time_end: str | None = Field(default=None, description="HH:MM (local)")
    time_zone: str | None = Field(default=None, max_length=64)
    context_required: dict[str, Any] | None = Field(default=None)


# ---------- Access ----------
class AccessRequestIn(BaseModel):
    asset_id: str
    purpose: str
    # Optional supporting context (policy-based, users never enter GPS).
    context: dict[str, Any] | None = Field(default=None)


class AccessRequestOut(BaseModel):
    id: str
    asset_id: str
    requester_id: str
    purpose: str
    status: str
    created_at: datetime
    context_provided: dict[str, Any] | None = None


class AccessDecision(BaseModel):
    decision: str = Field(pattern="^(approve|deny)$")
    duration_minutes: int = Field(default=30, ge=1, le=1440)


class GrantOut(BaseModel):
    id: str
    asset_id: str
    purpose: str
    granted_at: datetime
    expires_at: datetime


# ---------- Trust ----------
# V2 authoritative decision set.
DECISION_VALUES = "^(ALLOW|STEP_UP|RESTRICTED|DENY)$"


class TrustStateOut(BaseModel):
    user_id: str
    trust_score: int
    decision: str = Field(pattern=DECISION_VALUES)  # ALLOW | STEP_UP | RESTRICTED | DENY
    reasons: list[str]
    model_version: str
    timestamp: datetime
    components: dict[str, float]
    ml_signal: float | None = None


class SecurityEventIn(BaseModel):
    event_type: str
    user_id: str | None = None
    risk_signals: dict[str, Any] = Field(default_factory=dict)


class SecurityEventOut(BaseModel):
    id: str
    user_id: str | None
    event_type: str
    risk_signals: dict[str, Any]
    trust_score: int | None
    decision: str | None
    created_at: datetime


# ---------- Audit ----------
class AuditEventOut(BaseModel):
    event_id: str
    event_type: str
    trust_score: int | None
    decision: str | None
    risk_signals: dict[str, Any]
    created_at: datetime
    anchor: dict[str, Any] | None = None


# ---------- QR verification (V2) ----------
class QrGenerateRequest(BaseModel):
    credential_id: str
    purpose: str | None = None
    expires_minutes: int = Field(default=5, ge=1, le=60)


class QrGenerateResponse(BaseModel):
    qr_token: str
    qr_url: str
    expires_at: datetime


class QrVerifyRequest(BaseModel):
    qr_token: str


class QrVerifyResponse(BaseModel):
    id: str
    valid: bool
    status: str
    hash_match: bool
    holder_did: str | None = None
    type: str | None = None
    issuer_id: str | None = None
    issued_at: datetime | None = None
    purpose: str | None = None
    expires_at: datetime | None = None
    selective_disclosure_ready: bool = True
    explanation: str | None = None


# ---------- Asset ownership / NFT (V2) ----------
class AssetTransferRequest(BaseModel):
    to_user_id: str
    reason: str | None = None


class AssetTransferOut(BaseModel):
    id: str
    asset_id: str
    from_user_id: str
    to_user_id: str
    reason: str | None
    created_at: datetime


class AssetOwnershipOut(BaseModel):
    asset_id: str
    owner_id: str
    nft_token_id: str | None = None
    chain_tx_hash: str | None = None
    transferred_at: datetime | None = None
    history: list[dict[str, Any]] = Field(default_factory=list)


# ---------- Policy (V2 extended response) ----------
class AssetPolicyOut(BaseModel):
    id: str
    asset_id: str
    requester_role: str
    purpose: str
    min_trust: int
    expires_at: datetime | None
    location_scope: str | None = None
    location_strict: bool = False
    time_start: str | None = None
    time_end: str | None = None
    time_zone: str | None = None
    context_required: dict[str, Any] | None = None


# ---------- Human-friendly access decision (V2) ----------
class AccessDecisionReason(BaseModel):
    code: str
    human: str


class AccessDecisionOut(BaseModel):
    decision: str = Field(pattern=DECISION_VALUES)
    human: str
    next_action: str | None = None
    scope: str | None = None
    severity: str = "info"  # info | warning | critical
    trust_score: int | None = None
    reasons: list[str] = Field(default_factory=list)
    reasons_human: list[AccessDecisionReason] = Field(default_factory=list)
    model_version: str | None = None


# ---------- Offline capability (V2) ----------
class OfflineEventIn(BaseModel):
    event_type: str
    asset_id: str | None = None
    decision: str | None = None
    reasons: list[str] = Field(default_factory=list)
    trust_score: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    client_ts: datetime | None = None


class OfflineBatchIn(BaseModel):
    user_id: str | None = None
    events: list[OfflineEventIn] = Field(default_factory=list)


class OfflineEventOut(BaseModel):
    id: str
    event_type: str
    asset_id: str | None
    decision: str | None
    trust_score: int | None
    sync_status: str  # pending | failed | synced
    created_at: datetime


class OfflineSyncOut(BaseModel):
    received: int
    synced: int
    deduped: int
    failed: int


# ---------- Device recovery (V2) ----------
class DeviceRecoverRequest(BaseModel):
    reason: str | None = None


class DeviceRecoverOut(BaseModel):
    id: str
    user_id: str
    status: str  # pending | approved | denied
    reason: str | None = None
    requested_at: datetime


# ---------- Dashboard (V2) ----------
class DashboardSummary(BaseModel):
    user_role: str
    identities: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] = Field(default_factory=dict)
    assets: dict[str, Any] = Field(default_factory=dict)
    pending_requests: list[dict[str, Any]] = Field(default_factory=list)
    recent_activity: list[dict[str, Any]] = Field(default_factory=list)
    security_alerts: list[dict[str, Any]] = Field(default_factory=list)
    trust: dict[str, Any] | None = None
    technical: dict[str, Any] | None = None