"""AES-256-GCM encryption + SHA-256 hashing.

The application master key is resolved through a KeyManager (env-backed today,
KMS-backed in real deployments). Each object gets a unique 12-byte nonce; the
nonce travels beside the ciphertext. Callers SHOULD bind context via AAD
(credential id, purpose) so ciphertext cannot be replayed onto another object.
"""
import hashlib
import os
import warnings

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_DEV_FALLBACK = hashlib.sha256(b"trustvault-dev-only-key-do-not-use-in-prod").digest()

GCM_NONCE_LEN = 12
KEY_LEN = 32


class KeyManager:
    """Resolves the deployment master key.

    Backends:
      * env  — TRUSTVAULT_MASTER_KEY; dev fallback only when unset (loud warning).
    Future backends: aws-kms / azure-kv / vault, sharing this interface so no
    caller ever touches a plaintext key directly.
    """

    def __init__(self, provider: str = "env", raw: str = ""):
        self.provider = provider
        self._raw = raw

    def get_key(self) -> bytes:
        if self.provider != "env":
            raise RuntimeError(f"KeyManager provider '{self.provider}' not configured")
        raw = self._raw or os.environ.get("TRUSTVAULT_MASTER_KEY", "")
        if not raw:
            warnings.warn("No TRUSTVAULT_MASTER_KEY set; using DEV fallback key. DO NOT USE IN PRODUCTION.")
            return _DEV_FALLBACK
        if len(raw) < 32:
            warnings.warn("TRUSTVAULT_MASTER_KEY too short; deriving via SHA-256.")
        return hashlib.sha256(raw.encode()).digest()


def _load_key() -> bytes:
    from app.core.config import get_settings

    s = get_settings()
    return KeyManager(provider=s.master_key_provider, raw=s.master_key).get_key()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encrypt_bytes(plaintext: bytes, aad: bytes | None = None) -> tuple[bytes, bytes]:
    """Return (ciphertext, nonce). AAD is authenticated but not encrypted."""
    key = _load_key()
    nonce = os.urandom(GCM_NONCE_LEN)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad)
    return ct, nonce


def decrypt_bytes(ciphertext: bytes, nonce: bytes, aad: bytes | None = None) -> bytes:
    key = _load_key()
    return AESGCM(key).decrypt(nonce, ciphertext, aad)