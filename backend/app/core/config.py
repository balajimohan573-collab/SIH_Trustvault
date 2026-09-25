from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Database -----------------------------------------------------------
    # PostgreSQL is the authoritative application database. Override with
    # `sqlite:///./trustvault.db` for zero-dependency local development and
    # for the automated test-suite (tests set DATABASE_URL=sqlite://).
    database_url: str = (
        "postgresql+psycopg2://trustvault:trustvault_dev@localhost:5432/trustvault"
    )

    # --- Security -----------------------------------------------------------
    jwt_secret: str = "change-me-dev-secret"
    jwt_expiry_minutes: int = 15
    algorithm: str = "HS256"
    session_ttl_hours: int = 24  # persistent DB-backed sessions
    session_cookie_secure: bool = False  # set True behind TLS in production

    # Master data-encryption key. In development a raw value is accepted and
    # passed through a KeyManager; in production point to a KMS-backed key.
    master_key: str = ""
    master_key_provider: str = "env"  # env | (future) aws-kms | azure-kv | vault

    # Password-reset delivery. True returns the real token in the API response
    # for dev + e2e flows; production MUST disable this and email the token.
    reset_token_dev_delivery: bool = True

    # --- Storage ------------------------------------------------------------
    storage_dir: str = "./storage"
    storage_backend: str = "local"  # local | s3
    # S3-compatible settings (used when storage_backend=s3). Supports AWS S3,
    # Cloudflare R2, MinIO, Supabase Storage, Azure Blob via emulation.
    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_region: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # Upload limits + validation (see services/file_validation.py)
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
    allowed_upload_extensions: str = "pdf,png,jpg,jpeg"
    allowed_upload_mimetypes: str = (
        "application/pdf,image/png,image/jpeg,application/octet-stream"
    )

    # --- WebAuthn -----------------------------------------------------------
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "TrustVault"
    webauthn_origin: str = "http://localhost:5173"

    # --- Verification / QR --------------------------------------------------
    verification_base_url: str = "http://localhost:5173"  # public base for /verify links
    qr_expiry_minutes: int = 30

    # --- Blockchain ---------------------------------------------------------
    # Explicit opt-in. When disabled the application runs fully off-chain and
    # anchoring stays queued ("pending"). A transaction is NEVER fabricaged.
    chain_enabled: bool = False
    chain_network: str = "amoy"  # amoy (Polygon) | sepolia
    rpc_url: str = ""
    private_key: str = ""
    identity_registry_address: str = ""
    asset_registry_address: str = ""
    access_control_address: str = ""
    audit_registry_address: str = ""
    chain_id: int = 80002  # Polygon Amoy default (80002); Sepolia = 11155111

    # --- ML anomaly layer (off by default; advisory only, never grants) -----
    ml_anomaly_enabled: bool = False
    ml_restrict_threshold: float = -0.3
    ml_block_threshold: float = -0.6

    # --- Feature flags ------------------------------------------------------
    offline_enabled: bool = True
    duress_enabled: bool = False
    duress_ttl_minutes: int = 30
    notifications_enabled: bool = True
    maintainer_email: str = ""  # shown on the login screen / docs

    # --- CORS ---------------------------------------------------------------
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- Rate limiting (per client / window) --------------------------------
    rate_limit_max: int = 60
    rate_limit_window_seconds: int = 60
    # Stricter limit for credential-enumeration prone endpoints (login, register, reset)
    auth_rate_limit_max: int = 10
    auth_rate_limit_window_seconds: int = 300

    # --- Bootstrap admin ----------------------------------------------------
    # When set, init_db creates this guaranteed admin account (password is set
    # via TRUSTVAULT_ADMIN_PASSWORD first-boot; never committed to the repo).
    admin_email: str = "admin@trustvault.local"
    admin_password: str = ""

    # --- Issuer policy ------------------------------------------------------
    issuer_org_verification_required: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()