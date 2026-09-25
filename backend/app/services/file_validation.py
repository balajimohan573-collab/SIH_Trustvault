"""Upload validation: magic bytes, size limits, MIME cross-check.

The Content-Type header is untrusted; the *detected* type from magic bytes is
authoritative. Underlying hash/verify in services.file_validation.
"""
import hashlib
import re

from app.core.config import get_settings

MAGIC_SIGNATURES: list[tuple[str, str, bytes]] = [
    ("application/pdf", "pdf", b"%PDF-"),
    ("image/png", "png", b"\x89PNG\r\n\x1a\n"),
    ("image/jpeg", "jpg", b"\xff\xd8\xff"),
]

SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._ -]")


class FileValidationError(ValueError):
    pass


def detect_type(data: bytes) -> tuple[str, str] | None:
    """Return (detected_mime, detected_ext) from magic bytes, else None."""
    for mime, ext, sig in MAGIC_SIGNATURES:
        if data[: len(sig)] == sig:
            return mime, ext
    return None


def sanitize_filename(filename: str) -> str:
    cleaned = SAFE_FILENAME_RE.sub("_", filename or "upload").strip(" .")
    return cleaned[:200] or "upload"


def validate_upload(data: bytes, original_filename: str | None = None, content_type: str | None = None) -> dict:
    """Validate upload content against policy. Raises FileValidationError."""
    settings = get_settings()
    if not data:
        raise FileValidationError("Empty upload")
    if settings.max_upload_bytes > 0 and len(data) > settings.max_upload_bytes:
        raise FileValidationError(
            f"File too large: {len(data)} > {settings.max_upload_bytes} bytes"
        )

    detected = detect_type(data)
    if detected is None:
        raise FileValidationError("Unsupported file type — only PDF, PNG, JPG/JPEG are accepted")
    detected_mime, detected_ext = detected

    allowed_exts = {e.strip() for e in settings.allowed_upload_extensions.split(",") if e.strip()}
    if detected_ext not in allowed_exts:
        raise FileValidationError(f"Unsupported extension: .{detected_ext}")

    if content_type:
        allowed_mimes = {m.strip() for m in settings.allowed_upload_mimetypes.split(",") if m.strip()}
        normalized = content_type.split(";")[0].strip().lower()
        if normalized in allowed_mimes and detected_mime not in ("application/octet-stream",) and normalized != detected_mime:
            raise FileValidationError(
                f"Content-Type {normalized} does not match detected type {detected_mime}"
            )

    return {
        "original_filename": sanitize_filename(original_filename) if original_filename else "evidence",
        "content_type": detected_mime,
        "detected_ext": detected_ext,
        "detected_type": detected_mime,
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def is_valid_evidence(data: bytes) -> dict | None:
    """Best-effort evidence check for existing data (attachments without upload)."""
    try:
        return validate_upload(data, content_type=None)
    except FileValidationError:
        return None