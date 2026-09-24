"""V2: convert technical (decision, reason-codes) output into human-friendly
explanations for the dashboard and access UIs.

Decisions: ALLOW | STEP_UP | RESTRICTED | DENY. The same codes power the
technical view (model_version, components, checker, policy_id); only the human
layer is here.
"""
from app.schemas import AccessDecisionOut, AccessDecisionReason

_DECISION_TITLES = {
    "ALLOW": "Access allowed",
    "STEP_UP": "Step-up verification required",
    "RESTRICTED": "Access restricted — read-only / limited scope",
    "DENY": "Access denied",
}

_DECISION_NEXT = {
    "ALLOW": None,
    "STEP_UP": "Complete an additional verification (e.g. passkey re-assertion) to continue with full access.",
    "RESTRICTED": "Full access is limited to read-only. Additional verification or a corrected context may unlock full access.",
    "DENY": "You can retry after addressing the reason, or contact the resource owner / administrator.",
}

_DECISION_SEVERITY = {
    "ALLOW": "info",
    "STEP_UP": "warning",
    "RESTRICTED": "warning",
    "DENY": "critical",
}

_REASON_HUMAN = {
    "OK_CREDENTIAL": "Your identity credential is active and valid.",
    "OK": "All checks passed.",
    "UNAUTHENTICATED": "You are not authenticated.",
    "NO_CREDENTIAL": "No active identity credential is associated with this account.",
    "CREDENTIAL_REVOKED": "Your identity credential has been revoked. Contact the issuing institution.",
    "NEW_DEVICE": "This request came from a device we have not seen before.",
    "DEVICE_REVOKED": "The device used for this request has been revoked.",
    "KNOWN_DEVICE": "This request came from a known, active device.",
    "NO_DEVICE_TRACKING": "No device signal was available to evaluate.",
    "REQUEST_VELOCITY_HIGH": "Unusually high request activity was detected.",
    "REQUEST_VELOCITY_EXCESSIVE": "Request activity exceeded safe limits.",
    "UNUSUAL_HOUR": "The request was made outside the usual hours for this account.",
    "ANOMALY_DETECTED": "The AI anomaly monitor flagged this request.",
    "HISTORY_NORMAL": "Account history looks normal.",
    "HISTORY_ANOMALOUS": "Recent account activity contains anomalies.",
    "NO_POLICY_FOR_ROLE": "No access policy exists for your role on this asset.",
    "WRONG_PURPOSE": "The requested purpose is not permitted by the policy.",
    "NO_VALID_GRANT": "You do not have an approved, active access grant.",
    "GRANT_EXPIRED": "Your access grant has expired. Request a new one from the owner.",
    "ADMIN_OVERRIDE": "Access was granted through an explicit privileged administrator override (audited).",
    "NON_ADMIN_OVERRIDE_ATTEMPT": "A privileged override was attempted without the administrator role — recorded.",
    "TRUST_TOO_LOW": "Your current trust score is below the policy minimum.",
    "LOCATION_MISMATCH": "This asset is restricted to a specific location that does not match your current context.",
    "LOCATION_MISSING": "This asset is location-restricted but no location context was provided.",
    "TIME_OUTSIDE": "This asset is restricted to a time window that is not currently open.",
    "CONTEXT_REQUIRED": "This policy requires additional context that was not provided.",
    "RESTRICTED_ACCESS": "Access has been limited to read-only / restricted scope.",
}


def reason_human(code: str) -> str:
    return _REASON_HUMAN.get(code, f"Policy code {code}")


def build_decision_out(
    decision: str,
    reasons: list[str] | None = None,
    trust_score: int | None = None,
    model_version: str | None = None,
    scope: str | None = None,
) -> AccessDecisionOut:
    """Map a technical decision into a human-friendly, dashboard-ready object."""
    reasons = reasons or []
    human = _DECISION_TITLES.get(decision, decision)
    if scope == "read-only":
        human = "Access restricted — read-only / limited scope"
    return AccessDecisionOut(
        decision=decision,
        human=human,
        next_action=_DECISION_NEXT.get(decision),
        scope=scope,
        severity=_DECISION_SEVERITY.get(decision, "info"),
        trust_score=trust_score,
        reasons=reasons,
        reasons_human=[AccessDecisionReason(code=r, human=reason_human(r)) for r in reasons],
        model_version=model_version,
    )