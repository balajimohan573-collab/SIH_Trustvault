import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def uuid_str() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Decentralized identifier string (did:trustvault:<uuid>) or a DID method claim.
    did: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(64), default="holder")  # holder | issuer | verifier | admin
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    credentials_issued: Mapped[list["Credential"]] = relationship(
        foreign_keys="Credential.issuer_id", back_populates="issuer"
    )
    credentials_held: Mapped[list["Credential"]] = relationship(
        foreign_keys="Credential.holder_id", back_populates="holder"
    )
    devices: Mapped[list["Device"]] = relationship(back_populates="user")


class WebAuthnCredential(Base):
    """Passkey credential stored server-side for WebAuthn assertion/attestation."""

    __tablename__ = "webauthn_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )
    credential_id: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    issuer_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    holder_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. education_certificate
    # SHA-256 hash of the underlying document (never store the raw doc on-chain).
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | revoked
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    issuer: Mapped["User"] = relationship(foreign_keys=[issuer_id], back_populates="credentials_issued")
    holder: Mapped["User"] = relationship(foreign_keys=[holder_id], back_populates="credentials_held")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Path to the AES-256-GCM encrypted payload in local storage.
    encrypted_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    # SHA-256 hash of the raw plaintext bytes (integrity proof).
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Content identifier for a future IPFS/S3 backend. Nullable for now.
    cid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    # V2: NFT-backed ownership (ERC-721). Assigned on-chain (best-effort) or locally.
    nft_token_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    chain_tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    transferred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    asset_class: Mapped[str] = mapped_column(String(64), default="document")  # e.g. document|contract|record
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
    # V2: optional, policy-based location/time constraints (users never enter GPS).
    location_scope: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_strict: Mapped[bool] = mapped_column(Boolean, default=False)
    time_start: Mapped[str | None] = mapped_column(String(16), nullable=True)  # HH:MM
    time_end: Mapped[str | None] = mapped_column(String(16), nullable=True)  # HH:MM
    time_zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    context_required: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    asset: Mapped["Asset"] = relationship(back_populates="policies")


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id"), index=True, nullable=False)
    requester_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | approved | denied
    # V2: policy-declared context (location scope etc.) captured for audit.
    context_provided: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AccessGrant(Base):
    __tablename__ = "access_grants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id"), index=True, nullable=False)
    requester_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    asset: Mapped["Asset"] = relationship(back_populates="grants")


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    device_key_id: Mapped[str] = mapped_column(String(512), nullable=False)
    label: Mapped[str] = mapped_column(String(255), default="unnamed")
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | unknown | revoked

    user: Mapped["User"] = relationship(back_populates="devices")


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # Free-form JSONB risk signals (IP, device, velocity, fingerprints...).
    risk_signals: Mapped[dict] = mapped_column(JSON, default=dict)
    trust_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)  # ALLOW | STEP_UP | RESTRICTED | DENY
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditAnchor(Base):
    __tablename__ = "audit_anchors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    # "pending" until the Stage 6 anchoring service submits to Sepolia.
    tx_hash: Mapped[str] = mapped_column(String(66), default="pending", nullable=False)
    chain: Mapped[str] = mapped_column(String(32), default="sepolia")
    anchored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------- V2 models


class AssetTransfer(Base):
    """Ownership-transfer ledger for NFT-backed assets."""

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
    """Queue for offline decisions; reconciled with the audit trail on sync.

    `content_hash` is a SHA-256 over the canonical payload so re-uploads (e.g.
    duplicate network retries) are idempotent.
    """

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
    sync_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | failed | synced
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DeviceRecovery(Base):
    """Device-loss recovery requests (register new device / revoke stale one)."""

    __tablename__ = "device_recoveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | approved | denied
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DuressSession(Base):
    """Covert duress state. When active, sensitive access is restricted/frozen.

    Enforced only when `duress_enabled` is on; carries a short TTL.
    """

    __tablename__ = "duress_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    risk_signals: Mapped[dict] = mapped_column(JSON, default=dict)