import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.core.crypto import decrypt_bytes, encrypt_bytes, sha256_hex

settings = get_settings()


class StorageError(Exception):
    pass


@dataclass
class StoredObject:
    storage_uri: str  # object key (relative to the root / bucket)
    sha256: str
    byte_size: int


class StorageBackend:
    """Abstraction over encrypted object storage.

    Backends:
      * local — AES-256-GCM at rest on the local filesystem (default).
      * s3    — S3-compatible buckets (AWS S3, Cloudflare R2, MinIO). Requires
        a configured endpoint + credentials; otherwise raises StorageError so a
        misconfigured deployment fails loudly instead of pretending to store.
    """

    def __init__(self, backend: str = "local"):
        self.backend = backend

    def _root(self) -> Path:
        p = Path(settings.storage_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def save(self, plaintext: bytes, aad: bytes | None = None) -> StoredObject:
        """Encrypt with a unique nonce + AAD and persist. Returns object metadata."""
        file_hash = sha256_hex(plaintext)
        ciphertext, nonce = encrypt_bytes(plaintext, aad=aad)
        rel_path = f"{uuid.uuid4()}.enc"

        if self.backend == "local":
            abs_path = self._root() / rel_path
            try:
                abs_path.write_bytes(nonce + ciphertext)
            except OSError as exc:
                raise StorageError(f"Failed to write encrypted file: {exc}") from exc
        elif self.backend == "s3":
            raise StorageError(
                "S3 storage not configured. Set s3_endpoint/s3_bucket/s3_credentials or use storage_backend=local."
            )
        else:
            raise StorageError(f"Unknown storage backend: {self.backend}")

        return StoredObject(storage_uri=rel_path, sha256=file_hash, byte_size=len(plaintext))

    def load(self, storage_uri: str, expected_sha256: str | None = None, aad: bytes | None = None) -> bytes:
        """Decrypt and return the object. Verifies integrity hash when provided."""
        if self.backend == "local":
            abs_path = self._root() / os.path.basename(storage_uri)
            if not abs_path.exists():
                raise StorageError(f"Encrypted object not found: {storage_uri}")
            blob = abs_path.read_bytes()
            if len(blob) <= 12:
                raise StorageError("Corrupt encrypted object (too short)")
            nonce, ciphertext = blob[:12], blob[12:]
            plaintext = decrypt_bytes(ciphertext, nonce, aad=aad)
        elif self.backend == "s3":
            raise StorageError("S3 storage not configured.")
        else:
            raise StorageError(f"Unknown storage backend: {self.backend}")

        if expected_sha256 and sha256_hex(plaintext) != expected_sha256:
            raise StorageError("Decrypted object failed SHA-256 integrity check")
        return plaintext

    def delete(self, storage_uri: str) -> None:
        if self.backend != "local":
            return
        abs_path = self._root() / os.path.basename(storage_uri)
        if abs_path.exists():
            abs_path.unlink()


backend = StorageBackend(backend=settings.storage_backend)


# --- Legacy convenience functions (kept for the V2 assets feature) ----------


def save_encrypted(plaintext: bytes) -> tuple[str, str, str]:
    """Encrypt + store a file. Returns (object_key, storage_uri, plaintext_sha256)."""
    obj = backend.save(plaintext)
    return obj.storage_uri.replace(".enc", ""), obj.storage_uri, obj.sha256


def load_decrypted(relative_uri: str, expected_sha256: str | None = None) -> bytes:
    return backend.load(relative_uri, expected_sha256=expected_sha256)


def delete(relative_uri: str) -> None:
    backend.delete(relative_uri)