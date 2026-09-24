"""Access-control pipeline (identity + context + RBAC + ABAC). Evaluated in order:

 1. Is the identity authenticated?
 2. Is the credential valid and not revoked?
 3. Is the policy-declared context satisfied (location / time, if required)?
 4. Does the role have the requested permission (an asset policy matches)?
 5. Does the asset policy permit this purpose?
 6. Is the grant inside its validity window?
 7. Does the current trust score satisfy the policy minimum threshold?
 8. If not, can step-up authentication satisfy the required assurance?
 9. AI/ML may further restrict, reduce or freeze — never grant.
10. Record the final decision and reason codes.

V2 authoritative decisions: ALLOW | STEP_UP | RESTRICTED | DENY.

Hard failures (revocation, expiry, wrong purpose, strict context mismatch, no
policy, no grant) are DENY and are always authoritative over the numeric trust
score. Non-strict context mismatch degrades to RESTRICTED (read-only/limited).
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time, timedelta

from sqlalchemy.orm import Session

from app.models import (
    AccessGrant,
    AccessPolicy,
    Asset,
    Credential,
    DuressSession,
    SecurityEvent,
    User,
)
from app.core.config import get_settings
from app.services.trust import TrustState, STEP_UP_THRESHOLD, evaluate_trust
from app.services import anomaly  # optional ML signal (no-op unless enabled)

log = logging.getLogger("trustvault.policy")

# Decision codes produced by the pipeline (V2 authoritative set).
DECISION_ALLOW = "ALLOW"
DECISION_STEP_UP = "STEP_UP"
DECISION_RESTRICTED = "RESTRICTED"
DECISION_DENY = "DENY"

# Hard blockers/hints -> reason codes.
POLICY_REASON_CODES = {
    "no_policy": "NO_POLICY_FOR_ROLE",
    "wrong_purpose": "WRONG_PURPOSE",
    "no_grant": "NO_VALID_GRANT",
    "grant_expired": "GRANT_EXPIRED",
    "admin_override": "ADMIN_OVERRIDE",
    "location_mismatch": "LOCATION_MISMATCH",
    "location_missing": "LOCATION_MISSING",
    "time_outside": "TIME_OUTSIDE",
    "context_required": "CONTEXT_REQUIRED",
    "restricted_scope": "RESTRICTED_ACCESS",
    "duress_active": "DURESS_ACTIVE",
}


@dataclass
class PolicyDecision:
    decision: str  # ALLOW | STEP_UP | RESTRICTED | DENY
    trust_score: int
    reasons: list[str] = field(default_factory=list)
    policy_id: str | None = None
    model_version: str = "rules-v2"
    checker: list[str] = field(default_factory=list)  # steps satisfied so far
    scope: str | None = None  # e.g. "read-only" when RESTRICTED
    context_violation: str | None = None  # which context constraint failed


def _duress_active(db: Session, user_id: str) -> bool:
    session = (
        db.query(DuressSession)
        .filter(DuressSession.user_id == user_id, DuressSession.active.is_(True))
        .order_by(DuressSession.activated_at.desc())
        .first()
    )
    if session is None:
        return False
    if session.expires_at and session.expires_at < datetime.utcnow():
        session.active = False
        db.commit()
        return False
    return True


def _recent_events(db: Session, user_id: str, minutes: int = 1) -> list[SecurityEvent]:
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    return (
        db.query(SecurityEvent)
        .filter(SecurityEvent.user_id == user_id, SecurityEvent.created_at >= cutoff)
        .all()
    )


def build_context(
    db: Session,
    user: User,
    device_status: str | None = None,
    device_novel: bool | None = None,
    extra: dict | None = None,
) -> dict:
    """Assemble the flattened signal context the trust engine consumes."""
    extra = extra or {}
    creds = db.query(Credential).filter(Credential.holder_id == user.id).all()
    has_active = any(c.status == "active" for c in creds)
    revoked = any(c.status == "revoked" for c in creds)

    window = _recent_events(db, user.id, minutes=1)
    requests_in_window = sum(1 for e in window if e.event_type.startswith("access"))
    recent_failures = sum(1 for e in window if e.event_type == "auth_failed")
    recent_anomalies = sum(1 for e in window if e.decision == "BLOCK")

    now = datetime.utcnow()
    hour = None
    if extra.get("request_hour") is not None:
        hour = extra["request_hour"]
    elif "X-TrustVault-Hour" in extra.get("headers", {}):
        try:
            hour = int(extra["headers"]["X-TrustVault-Hour"])
        except (TypeError, ValueError):
            hour = now.hour
    else:
        hour = now.hour

    # Policy-based location: supplied by the environment/client context (never a
    # manual GPS entry by the requester).
    location_scope = (
        extra.get("location_scope")
        or extra.get("headers", {}).get("X-TrustVault-Location-Scope")
        or None
    )

    ml_signal = anomaly.score(user.id, extra) if anomaly.enabled() else None

    return {
        "identity": {
            "has_active_credential": has_active,
            "credential_revoked": revoked,
            "recent_auth_failures": recent_failures,
        },
        "device": {
            "status": device_status if device_status else ("unknown" if device_novel else "active"),
            "novel": bool(device_novel),
        },
        "behaviour": {
            "requests_per_minute": requests_in_window + extra.get("velocity_bonus", 0.0),
            "access_sequence": extra.get("access_sequence"),
        },
        "context": {
            "hour": hour,
            "geo_penalty": float(extra.get("geo_penalty", 0.0)),
            "location_scope": location_scope,
            "now": now,
        },
        "history": {
            "recent_anomalies": recent_anomalies,
        },
        "ml_signal": ml_signal,
    }


def _find_policy(db: Session, asset: Asset, user: User, purpose: str) -> AccessPolicy | None:
    policies = (
        db.query(AccessPolicy)
        .filter(AccessPolicy.asset_id == asset.id, AccessPolicy.requester_role == user.role)
        .all()
    )
    if not policies:
        return None
    for p in policies:
        if p.purpose == purpose:
            return p
    return policies[0]


def find_active_grant(db: Session, asset: Asset, user: User) -> AccessGrant | None:
    now = datetime.utcnow()
    return (
        db.query(AccessGrant)
        .filter(
            AccessGrant.asset_id == asset.id,
            AccessGrant.requester_id == user.id,
            AccessGrant.granted_at <= now,
            AccessGrant.expires_at > now,
        )
        .order_by(AccessGrant.granted_at.desc())
        .first()
    )


def find_latest_grant(db: Session, asset: Asset, user: User) -> AccessGrant | None:
    """Most recent grant (any status) — used to recover the intended purpose
    even when the grant is already expired (so the expiry reason can surface)."""
    return (
        db.query(AccessGrant)
        .filter(AccessGrant.asset_id == asset.id, AccessGrant.requester_id == user.id)
        .order_by(AccessGrant.granted_at.desc())
        .first()
    )


def _parse_hhmm(value: str) -> dt_time | None:
    try:
        h, m = value.strip().split(":")
        return dt_time(int(h), int(m))
    except (ValueError, AttributeError):
        return None


def _minutes_of_day(t: dt_time) -> int:
    return t.hour * 60 + t.minute


def _time_in_window(now: datetime, start: str, end: str) -> bool:
    s, e = _parse_hhmm(start), _parse_hhmm(end)
    if s is None or e is None:
        return True  # malformed policy -> treat as unconstrained
    now_min = _minutes_of_day(now.time())
    s_min, e_min = _minutes_of_day(s), _minutes_of_day(e)
    if s_min <= e_min:
        return s_min <= now_min < e_min
    return now_min >= s_min or now_min < e_min  # overnight window


def _check_context(
    policy: AccessPolicy, context: dict
) -> tuple[bool, str | None, str | None]:
    """Evaluate policy-declared context constraints (location / time).

    Returns (ok, violation_reason_code, scope). Location is policy-based and
    optional; the requester never supplies raw GPS coordinates.
    """
    if policy is None:
        return True, None, None
    ctx = context.get("context", {}) if isinstance(context, dict) else {}

    if policy.location_scope:
        provided = ctx.get("location_scope")
        if not provided:
            return False, POLICY_REASON_CODES["location_missing"], "read-only"
        if provided != policy.location_scope:
            return False, POLICY_REASON_CODES["location_mismatch"], "read-only"

    if policy.time_start or policy.time_end:
        now = ctx.get("now") or datetime.utcnow()
        if policy.time_start and policy.time_end and not _time_in_window(
            now, policy.time_start, policy.time_end
        ):
            return False, POLICY_REASON_CODES["time_outside"], "read-only"

    return True, None, None


def evaluate_access(
    db: Session,
    user: User,
    asset: Asset,
    purpose: str,
    context: dict,
    *,
    admin_override: bool = False,
    check_grant: bool = True,
) -> PolicyDecision:
    """Run the full pipeline for a data access evaluation.

    Returns an authoritative decision from {ALLOW, STEP_UP, RESTRICTED, DENY}.
    """
    checker: list[str] = []
    reasons: list[str] = []

    # 1. Authenticated — guaranteed by the API layer, asserted here anyway.
    if not user or user.status != "active":
        return PolicyDecision(
            DECISION_DENY, 0, ["UNAUTHENTICATED"], checker=["authenticated(fail)"]
        )

    trust = evaluate_trust(context)

    # 0. Duress gate: while a covert duress session is active, sensitive access
    #    is frozen outright (enforced only when the deployment opts in).
    if get_settings().duress_enabled and _duress_active(db, user.id):
        return PolicyDecision(
            DECISION_DENY,
            trust.trust_score,
            [POLICY_REASON_CODES["duress_active"]],
            model_version=trust.model_version,
            checker=checker,
        )

    # 7. Admin override (evaluated up-front): ALLOW only for the admin role,
    #     always leaving an explicit privileged reason code. The caller is
    #     responsible for persisting a privileged audit entry.
    if admin_override:
        if user.role != "admin":
            return PolicyDecision(
                DECISION_DENY, trust.trust_score, ["NON_ADMIN_OVERRIDE_ATTEMPT"],
                model_version=trust.model_version, checker=checker,
            )
        return PolicyDecision(
            DECISION_ALLOW,
            trust.trust_score,
            [POLICY_REASON_CODES["admin_override"]],
            model_version=trust.model_version,
            checker=checker + ["admin_override"],
        )

    # 2. Credential valid and not revoked.
    if trust.hard_block in ("CREDENTIAL_REVOKED", "DEVICE_REVOKED"):
        return PolicyDecision(
            DECISION_DENY, trust.trust_score, [trust.hard_block], model_version=trust.model_version,
            checker=checker,
        )
    if not context["identity"]["has_active_credential"]:
        return PolicyDecision(
            DECISION_DENY, trust.trust_score, ["NO_CREDENTIAL"], model_version=trust.model_version,
            checker=checker,
        )

    # 3. Role permission: an asset policy exists for this role.
    policy = _find_policy(db, asset, user, purpose)
    if policy is None:
        return PolicyDecision(
            DECISION_DENY,
            trust.trust_score,
            [POLICY_REASON_CODES["no_policy"]] + trust.reasons,
            model_version=trust.model_version,
            checker=checker,
        )
    checker.append("policy")

    # 4. Context gate: policy-declared location/time constraints (optional).
    ok, violation, scope = _check_context(policy, context)
    if not ok:
        if policy.location_strict:
            return PolicyDecision(
                DECISION_DENY,
                trust.trust_score,
                [violation] + trust.reasons,
                policy_id=policy.id,
                model_version=trust.model_version,
                checker=checker,
                scope=scope,
                context_violation=violation,
            )
        return PolicyDecision(
            DECISION_RESTRICTED,
            trust.trust_score,
            [violation, POLICY_REASON_CODES["restricted_scope"]] + trust.reasons,
            policy_id=policy.id,
            model_version=trust.model_version,
            checker=checker,
            scope="read-only",
            context_violation=violation,
        )
    checker.append("context")

    # 5. Purpose permitted by the policy.
    if policy.purpose != purpose:
        return PolicyDecision(
            DECISION_DENY,
            trust.trust_score,
            [POLICY_REASON_CODES["wrong_purpose"]] + trust.reasons,
            policy_id=policy.id,
            model_version=trust.model_version,
            checker=checker,
        )
    checker.append("purpose")

    # 6. Grant validity window.
    if check_grant:
        grant = find_active_grant(db, asset, user)
        if grant is None:
            past_grant = (
                db.query(AccessGrant)
                .filter(AccessGrant.asset_id == asset.id, AccessGrant.requester_id == user.id)
                .first()
            )
            code = POLICY_REASON_CODES["grant_expired"] if past_grant else POLICY_REASON_CODES["no_grant"]
            return PolicyDecision(
                DECISION_DENY,
                trust.trust_score,
                [code] + trust.reasons,
                policy_id=policy.id,
                model_version=trust.model_version,
                checker=checker,
            )
        checker.append("grant")

    # 7. Trust score satisfies the policy minimum.
    if trust.trust_score < policy.min_trust:
        reasons.append("TRUST_TOO_LOW")

    # 8/9/10. Collapse trust decision into the final 4-way decision.
    if trust.decision == DECISION_DENY or trust.trust_score < STEP_UP_THRESHOLD:
        decision = DECISION_DENY
    elif "TRUST_TOO_LOW" in reasons:
        decision = DECISION_STEP_UP
    else:
        decision = trust.decision  # ALLOW | STEP_UP | RESTRICTED (ML-only restricts)

    return PolicyDecision(
        decision,
        trust.trust_score,
        (reasons + trust.reasons) or ["OK"],
        policy_id=policy.id,
        model_version=trust.model_version,
        checker=checker,
    )


def record_event(
    db: Session,
    user_id: str | None,
    event_type: str,
    decision: PolicyDecision | None = None,
    **risk_signals,
) -> SecurityEvent:
    evt = SecurityEvent(
        user_id=user_id,
        event_type=event_type,
        risk_signals={
            "policy_id": decision.policy_id if decision else None,
            "reasons": list(decision.reasons) if decision else [],
            **risk_signals,
        },
        trust_score=decision.trust_score if decision else None,
        decision=decision.decision if decision else None,
    )
    db.add(evt)
    db.commit()
    db.refresh(evt)
    return evt