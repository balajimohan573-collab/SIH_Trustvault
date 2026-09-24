from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "sqlite:///./trustvault.db"

    # Security
    jwt_secret: str = "change-me-dev-secret"
    jwt_expiry_minutes: int = 15
    algorithm: str = "HS256"

    # Storage
    storage_dir: str = "./storage"

    # WebAuthn
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "TrustVault"
    webauthn_origin: str = "http://localhost:5173"

    # Blockchain
    rpc_url: str = ""
    private_key: str = ""
    identity_registry_address: str = ""
    asset_registry_address: str = ""
    access_control_address: str = ""
    audit_registry_address: str = ""
    chain_id: int = 11155111
    # Explicit opt-in: only submit transactions when this is true. Keeps tests
    # and offline demos deterministic (anchors stay "pending").
    chain_enabled: bool = False

    # ML anomaly layer (off by default)
    ml_anomaly_enabled: bool = False
    ml_restrict_threshold: float = -0.3  # moderate anomaly -> may RESTRICT (AI never grants)
    ml_block_threshold: float = -0.6  # strong anomaly -> DENY

    # V2 flags
    offline_enabled: bool = True  # offline capability queue + sync
    duress_enabled: bool = False  # optional duress mode (covert alert + freeze)
    qr_expiry_minutes: int = 5  # short-lived QR verification tokens
    duress_ttl_minutes: int = 30

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Rate limiting (max requests per window per client)
    rate_limit_max: int = 60
    rate_limit_window_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()