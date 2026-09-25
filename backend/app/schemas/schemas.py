from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


# ---------- Auth ----------
class RegisterRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="holder", pattern="^(holder|issuer|verifier|admin)$")


class RegisterStartRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="holder", pattern="^(holder|issuer|verifier|admin)$")


class PasswordRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class PasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasskeyCompleteRequest(BaseModel):
    email: EmailStr
    # WebAuthn client/authenticator response JSON
    credential: dict[str, Any]
    label: str = "default"


class LoginStartRequest(BaseModel):
    email: EmailStr


class DeviceRegisterRequest(BaseModel):
    label: str = "default"


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetCompleteRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


# ---------- Credentials ----------
class CredentialClaimIn(BaseModel):
    key: str = Field(min_length=1, max_length=128)
    value: str
    claim_type: str = Field(default="string", max_length=32)
    public: bool = False


class CredentialIssueRequest(BaseModel):
    holder_email: EmailStr | None = None
    type: str = Field(min_length=1, max_length=128)
    title: str | None = None
    external_id: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None
    # Structured claims (the authoritative digital record).
    claims: list[CredentialClaimIn] = Field(default_factory=list)
    # Raw document object (kept for the legacy "document" payload shape).
    document: dict[str, Any] = Field(default_factory=dict)
    document_base64: str | None = None


class CredentialClaimOut(BaseModel):
    key: str
    value: str
    claim_type: str = "string"
    public: bool = False


class CredentialFileOut(BaseModel):
    id: str
    original_filename: str
    sha256: str
    byte_size: int
    content_type: str
    detected_type: str
    is_primary: bool


class CredentialResponse(BaseModel):
    id: str
    type: str
    title: str | None = None
    issuer_name: str | None = None
    issuer_org_id: str
    issuer_user_id: str
    holder_id: str
    status: str
    issue_date: str | None = None
    expiry_date: str | None = None
    external_id: str | None = None
    claims_hash: str
    hash: str | None = None
    anchor_tx_hash: str | None = None
    issued_at: datetime
    revoked_at: datetime | None = None
    suspended_at: datetime | None = None
    claims: list[CredentialClaimOut] = Field(default_factory=list)
    files: list[CredentialFileOut] = Field(default_factory=list)


class ValidateEvidenceRequest(BaseModel):
    content_type: str | None = None


class VerifyResponse(BaseModel):
    id: str
    valid: bool
    status: str
    hash_match: bool
    purpose: str | None = None


class PublicVerifyResponse(BaseModel):
    valid: bool
    result: str  # VERIFIED | INVALID | EXPIRED | REVOKED
    status: str
    credential_id: str | None = None
    holder_did: str | None = None
    holder_name: str | None = None
    type: str | None = None
    issuer_org: str | None = None
    issued_at: datetime | None = None
    expiry_date: str | None = None
    public_claims: dict[str, str] = Field(default_factory=dict)
    checks: dict[str, bool] = Field(default_factory=dict)
    reason: str | None = None
    purpose: str | None = None


class RevokeRequest(BaseModel):
    reason: str | None = None


class SuspendRequest(BaseModel):
    reason: str | None = None


# ---------- Organizations ----------
class OrganizationApplyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    official_domain: str = Field(min_length=3, max_length=255)
    org_identifier: str | None = Field(default=None, max_length=128)
    evidence_uri: str | None = Field(default=None, max_length=512)


class OrganizationOut(BaseModel):
    id: str
    name: str
    official_domain: str
    org_identifier: str | None = None
    verification_status: str
    verified_at: datetime | None = None
    created_at: datetime


class OrganizationDecideRequest(BaseModel):
    approve: bool
    note: str | None = None


# ---------- Notification ----------
class NotificationOut(BaseModel):
    id: str
    type: str
    title: str
    body: str
    link: str | None = None
    read: bool
    created_at: datetime


# ---------- Trusted devices ----------
class TrustedDeviceOut(BaseModel):
    id: str
    label: str
    browser: str | None = None
    os: str | None = None
    first_seen: datetime
    last_seen: datetime
    status: str


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
    location_scope: str | None = Field(default=None, max_length=255)
    location_strict: bool = Field(default=False)
    time_start: str | None = Field(default=None, description="HH:MM (local)")
    time_end: str | None = Field(default=None, description="HH:MM (local)")
    time_zone: str | None = Field(default=None, max_length=64)
    context_required: dict[str, Any] | None = Field(default=None)


# ---------- Asset access (V2) ----------
class AccessRequestIn(BaseModel):
    asset_id: str
    purpose: str
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


# ---------- Credential access (purpose-bound) ----------
class CredentialAccessRequestIn(BaseModel):
    credential_id: str
    purpose: str = Field(min_length=3, max_length=255)
    requested_claims: list[str] = Field(default_factory=list)
    expires_minutes: int = Field(default=60, ge=5, le=4320)


class CredentialAccessRequestOut(BaseModel):
    id: str
    credential_id: str
    requester_id: str
    purpose: str
    requested_claims: list[str]
    status: str
    expires_at: datetime
    created_at: datetime
    decided_at: datetime | None = None


class CredentialAccessDecision(BaseModel):
    duration_minutes: int = Field(default=60, ge=5, le=4320)


class CredentialAccessGrantOut(BaseModel):
    id: str
    credential_id: str
    requester_id: str
    purpose: str
    allowed_claims: list[str]
    status: str
    granted_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None


class CredentialContentOut(BaseModel):
    credential_id: str
    holder_did: str
    type: str
    issued_at: datetime | None = None
    purpose: str
    claims: dict[str, str]
    granted_until: datetime


# ---------- Trust ----------
DECISION_VALUES = "^(ALLOW|STEP_UP|RESTRICTED|DENY)$"


class TrustStateOut(BaseModel):
    user_id: str
    trust_score: int
    decision: str = Field(pattern=DECISION_VALUES)
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
    severity: str = "info"
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