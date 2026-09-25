"""Authoritative compliance audit trail (audit_events).

Every sensitive action writes one row here: who, what, on what, result, reason,
and safe metadata. No passwords, no keys, no document bytes — only references.

Also exposes progress on anchoring high-value events (see audit.py for the
tx queue; anchors are best-effort and never fabricated).
"""
import logging

from sqlalchemy.orm import Session

from app.models import AuditEvent

log = logging.getLogger("trustvault.audit_trail")


def record(
    db: Session,
    actor_id: str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    result: str = "success",
    reason: str | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    """Persist one immutable audit row and return it."""
    row = AuditEvent(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result,
        reason=reason,
        meta=metadata or {},
    )
    db.add(row)
    db.flush()
    log.info("audit %s by=%s resource=%s:%s result=%s", action, actor_id, resource_type, resource_id, result)
    return row


def log_access(
    db: Session,
    actor_id: str | None,
    action: str,
    resource_type: str | None,
    resource_id: str | None,
    allowed: bool,
    reason: str | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    return record(
        db,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result="success" if allowed else "denied",
        reason=reason,
        metadata=metadata,
    )