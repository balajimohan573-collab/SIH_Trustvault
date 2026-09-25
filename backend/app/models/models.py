"""Authoritative relational schema for TrustVault.

PostgreSQL is the authoritative application database. The schema models real
identity, credential lifecycle, purpose-bound access, verification, sessions,
trusted devices, notifications and an immutable audit trail.

Design rules:
  * UUID string primary keys.
  * Foreign keys with indexes everywhere associations exist.
  * Check-like constraints via SQLAlchemy CheckConstraint where portable.
  * JSON columns keep their values opaque to the relational layer but are used
    only for genuinely unstructured data (claim allow-lists, risk signals).
  * No plaintext passwords, no secrets, no sensitive document bytes in schema.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def uuid_str() -> str:
    return str(uuid.uuid4())


# --------------------------------------------------------------------------
# Enumerations (kept as strings for SQLite/PostgreSQL portability)
# --------------------------------------------------------------------------

ROLES = ("holder", "issuer", "verifier", "admin")

ACCOUNT_STATUSES = ("active", "inactive", "locked")

# Credential lifecycle states (section 4 of the requirements).
CREDENTIAL_STATUSES = ("active", "expired", "revoked", "suspended")

ORGANIZATION_STATUSES = ("pending", "verified", "rejected")

ACCESS_REQUEST_STATUSES = ("pending", "approved", "denied", "expired", "cancelled")

GRANT_STATUSES = ("active", "revoked", "expired")

VERIFICATION_RESULTS = ("VERIFIED", "INVALID", "EXPIRED", "REVOKED")

# --------------------------------------------------------------------------
# Users + organizations
# --------------------------------------------------------------------------


class User(Base):
    """A real account. `password_hash` is bcrypt-only; `did` is a stable
    decentralized identifier used by the W3C-compatible credential output."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('holder','issuer','verifier','admin')", name="ck_users_role"),
        CheckConstraint(
            "status IN ('active','inactive','locked')", name="ck_users_account_status"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="holder")
    status: Mapped[str] = mapped_column(String(32), default="active")
    did: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id"), index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    organization: Mapped["Organization | None"] = relationship(back_populates="members")
    threads_devices: Mapped[list["TrustedDevice"]] = relationship(back_populates="user")
    sessions: Mapped[list["Session"]] = relationship(back_populates="user")
    credentials_issued: Mapped[list["Credential"]] = relationship(
        foreign_keys="Credential.issuer_user_id", back_populates="issuer_user"
    )
    credentials_held: Mapped[list["Credential"]] = relationship(
        foreign_keys="Credential.holder_id", back_populates="holder"
    )


class Organization(Base):
    """A real institution (university, trainer, employer). Not every user is
    an issuer — only users bound to a VERIFIED organization may issue."""

    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('pending','verified','rejected')",
            name="ck_orgs_verification_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    official_domain: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    org_identifier: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), default="pending")
    # Evidence supplied at registration (optional document hash / reference).
    evidence_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    members: Mapped[list["User"]] = relationship(back_populates="organization")
    issued_credentials: Mapped[list["Credential"]] = relationship(back_populates="issuer_org")


# --------------------------------------------------------------------------
# Credentials (the structured digital credential, NOT the PDF)
# --------------------------------------------------------------------------


class Credential(Base):
    """A structured digital credential record.

    The uploaded PDF/PNG/JPG is *supporting evidence* (CredentialFile). The
    authoritative record lives here: holder, issuer org, type, dates, claims,
    status, and a canonical claims hash for integrity + W3C VC interoperability.
    """

    __tablename__ = "credentials"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','expired','revoked','suspended')",
            name="ck_credentials_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    api_verification_token: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    holder_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )
    issuer_org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), index=True, nullable=False
    )
    issuer_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )
    issuer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[str] = mapped_column(String(128), nullable=False)  # e.g. BACHELOR_DEGREE
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)  # university ref no.
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    issue_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expiry_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # SHA-256 over the canonical claims JSON (integrity of the digital record).
    claims_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # SHA-256 over the primary evidence file (kept for back-compat reads).
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Best-effort chain anchor reference; "pending" means queued, None = never.
    anchor_tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)

    holder: Mapped["User"] = relationship(
        foreign_keys=[holder_id], back_populates="credentials_held"
    )
    issuer_user: Mapped["User"] = relationship(
        foreign_keys=[issuer_user_id], back_populates="credentials_issued"
    )
    issuer_org: Mapped["Organization"] = relationship(back_populates="issued_credentials")
    claims: Mapped[list["CredentialClaim"]] = relationship(
        back_populates="credential", cascade="all, delete-orphan"
    )
    files: Mapped[list["CredentialFile"]] = relationship(
        back_populates="credential", cascade="all, delete-orphan"
    )
    issuance_records: Mapped[list["CredentialIssuer"]] = relationship(
        back_populates="credential", cascade="all, delete-orphan"
    )


class CredentialClaim(Base):
    """A single claim inside a credential. `public` claims are shown by default
    in verification output; `private` claims must be explicitly granted."""

    __tablename__ = "credential_claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credentials.id"), index=True, nullable=False
    )
    claim_key: Mapped[str] = mapped_column(String(128), nullable=False)
    claim_value: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(32), default="string")
    public: Mapped[bool] = mapped_column(Boolean, default=False)  # shown on public verify
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    credential: Mapped["Credential"] = relationship(back_populates="claims")


class CredentialFile(Base):
    """Supporting evidence document (PDF/PNG/JPG).

    `storage_uri` points at the *encrypted* object in StorageService. Plaintext
    is never stored. `sha256` is the hash of the original plaintext bytes so
    integrity can be proven without decrypting.
    """

    __tablename__ = "credential_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credentials.id"), index=True, nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    detected_type: Mapped[str] = mapped_column(String(128), nullable=False)  # magic-byte result
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    credential: Mapped["Credential"] = relationship(back_populates="files")


class CredentialIssuer(Base):
    """Issuance ledger: who issued this credential, from which org, when."""

    __tablename__ = "credential_issuers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credentials.id"), index=True, nullable=False
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False)
    issuer_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)

    credential: Mapped["Credential"] = relationship(back_populates="issuance_records")


class Revocation(Base):
    """Revocation ledger. Issuer or holder may revoke; every revocation is
    audited and queued for on-chain anchoring (hash-proof, not data)."""

    __tablename__ = "revocations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credentials.id"), index=True, nullable=False
    )
    revoked_by: Mapped[str] = mapped_column(String(36), nullable=False)
    revoke_type: Mapped[str] = mapped_column(String(32), default="issuer")  # issuer|holder|admin
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    anchor_tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --------------------------------------------------------------------------
# Purpose-bound access (holder-controlled sharing)
# --------------------------------------------------------------------------


class CredentialAccessRequest(Base):
    """A verifier's request to view *permitted claims* of a credential for a
    stated purpose. The holder approves/denies; approval creates a
    CredentialAccessGrant whose enforcement is server-side and purpose-bound."""

    __tablename__ = "credential_access_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','denied','expired','cancelled')",
            name="ck_cr_access_requests_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credentials.id"), index=True, nullable=False
    )
    requester_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    permission: Mapped[str] = mapped_column(String(32), default="read")
    requested_claims: Mapped[list] = mapped_column(JSON, default=list)  # claim keys
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class CredentialAccessGrant(Base):
    """An active, purpose-bound & claim-scoped grant on a credential. Server
    enforcement re-checks status, purpose, allowed claims and expiry on every
    `/access/content` call — the holder can revoke at any time."""

    __tablename__ = "credential_access_grants"
    __table_args__ = (
        CheckConstraint("status IN ('active','revoked','expired')", name="ck_cr_access_grants_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credentials.id"), index=True, nullable=False
    )
    requester_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    permission: Mapped[str] = mapped_column(String(32), default="read")
    allowed_claims: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)


# --------------------------------------------------------------------------
# Verification + evidence of verification
# --------------------------------------------------------------------------


class VerificationEvent(Base):
    """Every public /verify call. Stores only the outcome + which checks ran —
    never the requester's identity unless they were authenticated."""

    __tablename__ = "verification_events"
    __table_args__ = (
        CheckConstraint(
            "result IN ('VERIFIED','INVALID','EXPIRED','REVOKED')",
            name="ck_verification_events_result",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credentials.id"), index=True, nullable=False
    )
    verification_token: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    checks: Mapped[dict] = mapped_column(JSON, default=dict)
    verifier_org_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --------------------------------------------------------------------------
# Security + audit
# --------------------------------------------------------------------------


class SecurityEvent(Base):
    """Risk telemetry feeding the trust engine (velocity, failures, anomalies)."""

    __tablename__ = "security_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_signals: Mapped[dict] = mapped_column(JSON, default=dict)
    trust_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditEvent(Base):
    """Authoritative, append-only compliance trail. Never stores passwords,
    keys or document contents — only safe metadata references."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    actor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    result: Mapped[str] = mapped_column(String(32), default="success")  # success|denied|failure
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AuditAnchor(Base):
    """On-chain anchor queue. `pending` rows submit to the configured network on
    startup/sync; a real tx hash is only ever written after a real transaction."""

    __tablename__ = "audit_anchors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tx_hash: Mapped[str] = mapped_column(String(66), default="pending", nullable=False)
    chain: Mapped[str] = mapped_column(String(32), default="amoy")
    anchored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --------------------------------------------------------------------------
# Authentication sessions + device trust
# --------------------------------------------------------------------------


class Session(Base):
    """Persistent DB-backed session. The JWT carries `jti`; the authoritative
    session state (issued/revoked/expired) lives here so sessions survive app
    restarts and can be revoked server-side."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )
    jti: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ip_addr: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")


class TrustedDevice(Base):
    """Privacy-conscious device recognition. Identifies a device by a key we
    generate server-side (derived from signals, never raw fingerprints stored
    in full). Users can view and remove devices."""

    __tablename__ = "trusted_devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )
    device_key_id: Mapped[str] = mapped_column(String(512), nullable=False)
    label: Mapped[str] = mapped_column(String(255), default="Untrusted device")
    browser: Mapped[str | None] = mapped_column(String(128), nullable=True)
    os: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(32), default="unknown")  # trusted|unknown|revoked

    user: Mapped["User"] = relationship(back_populates="threads_devices")


class WebAuthnCredential(Base):
    """Passkey credential for passwordless login and STEP_UP re-authentication."""

    __tablename__ = "webauthn_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )
    credential_id: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --------------------------------------------------------------------------
# Notifications + real-time events
# --------------------------------------------------------------------------


class Notification(Base):
    """In-app notification (MVP). Later: email/push via the same record."""

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)  # access_request, verified...
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


# --------------------------------------------------------------------------
# Legacy / V2 feature tables kept for compatibility
# --------------------------------------------------------------------------


class Asset(Base):
    """General secured document container (V2 NFT-backed asset flows)."""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    cid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    nft_token_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    chain_tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    transferred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    asset_class: Mapped[str] = mapped_column(String(64), default="document")
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    policies: Mapped[list["AccessPolicy"]] = relationship(back_populates="asset")
    grants: Mapped[list["AccessGrant"]] = relationship(back_populates="asset")
    transfers: Mapped[list["AssetTransfer"]] = relationship(back_populates="asset")


class AccessPolicy(Base):
    __tablename__ = "access_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id"), index=True, nullable=False)
    requester_role: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    min_trust: Mapped[int] = mapped_column(Integer, default=0)
    location_scope: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_strict: Mapped[bool] = mapped_column(Boolean, default=False)
    time_start: Mapped[str | None] = mapped_column(String(16), nullable=True)
    time_end: Mapped[str | None] = mapped_column(String(16), nullable=True)
    time_zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    context_required: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    asset: Mapped["Asset"] = relationship(back_populates="policies")


class AccessRequest(Base):
    """V2 asset-based access request (secured documents / NFT flows)."""

    __tablename__ = "access_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id"), index=True, nullable=False)
    requester_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    context_provided: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AccessGrant(Base):
    """V2 asset-based access grant (secured documents)."""

    __tablename__ = "access_grants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id"), index=True, nullable=False)
    requester_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active")

    asset: Mapped["Asset"] = relationship(back_populates="grants")


class AssetTransfer(Base):
    __tablename__ = "asset_transfers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id"), index=True, nullable=False)
    from_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    to_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    chain_tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    asset: Mapped["Asset"] = relationship(back_populates="transfers")


class OfflineEvent(Base):
    __tablename__ = "offline_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=True
    )
    asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    trust_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    client_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sync_status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DeviceRecovery(Base):
    __tablename__ = "device_recoveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DuressSession(Base):
    __tablename__ = "duress_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    risk_signals: Mapped[dict] = mapped_column(JSON, default=dict)