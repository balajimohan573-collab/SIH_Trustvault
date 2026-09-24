"""Trust Engine V2 — rules-based, explainable.

Weighted components:
    Identity    30%   (credential validity, recent auth failures)
    Device      20%   (known/active vs new/revoked)
    Behaviour   20%   (request velocity/bursts, access sequence)
    Context     15%   (unusual hour, unusual profile)
    History     15%   (past decisions/normalcy)

Trust score 0..100 maps to:
    >= 70  -> ALLOW
    40-69  -> STEP_UP
    <  40  -> DENY

V2 authoritative decision set: ALLOW | STEP_UP | RESTRICTED | DENY.

AI/ML restriction (downward only):
    - Moderate anomaly  (-0.6 <= ml_signal < -0.3): maybe RESTRICTED
    - Strong anomaly    (ml_signal < -0.6):                    -> DENY
    The ML signal can only restrict/reduce/freeze a decision. There is NO path
    from a negative ML signal to a higher-privilege decision.

Hard policy failures (revoked credential, expired/no grant, wrong purpose,
no policy) short-circuit to DENY regardless of the numeric score.
"""
import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("trustvault.trust")

WEIGHTS = {
    "identity": 0.30,
    "device": 0.20,
    "behaviour": 0.20,
    "context": 0.15,
    "history": 0.15,
}

ALLOW_THRESHOLD = 70
STEP_UP_THRESHOLD = 40

# AI/ML restriction thresholds (non-increasing effect only).
ML_RESTRICT_THRESHOLD = -0.3  # moderate anomaly -> can RESTRICT
ML_BLOCK_THRESHOLD = -0.6  # strong anomaly -> DENY

MODEL_VERSION = "rules-v2"

REASON_MESSAGES = {
    "OK_CREDENTIAL": "Active credential present",
    "NO_CREDENTIAL": "No active credential for requester",
    "CREDENTIAL_REVOKED": "Requester's credential is revoked",
    "NEW_DEVICE": "Authentication from a previously unseen device",
    "DEVICE_REVOKED": "Requester device is revoked",
    "KNOWN_DEVICE": "Authentication from a known active device",
    "NO_DEVICE_TRACKING": "No device signal available for scoring",
    "REQUEST_VELOCITY_HIGH": "Abnormally high request frequency",
    "REQUEST_VELOCITY_EXCESSIVE": "Request frequency exceeds hard threshold",
    "UNUSUAL_HOUR": "Request during an unusual time window",
    "ANOMALY_DETECTED": "Isolation Forest flagged the request as anomalous",
    "HISTORY_NORMAL": "Prior history within normal band",
    "HISTORY_ANOMALOUS": "Prior history shows anomalies",
}


@dataclass
class TrustState:
    trust_score: int
    decision: str  # ALLOW | STEP_UP | RESTRICTED | DENY
    reasons: list[str] = field(default_factory=list)
    components: dict[str, float] = field(default_factory=dict)
    ml_signal: float | None = None
    model_version: str = MODEL_VERSION
    hard_block: str | None = None  # reason code of a hard policy failure, if any


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def _score_identity(user_flags: dict[str, Any]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    if user_flags.get("credential_revoked"):
        return 0.0, ["CREDENTIAL_REVOKED"]
    if not user_flags.get("has_active_credential", True):
        return 30.0, ["NO_CREDENTIAL"]
    reasons.append("OK_CREDENTIAL")
    score = 100.0
    fails = user_flags.get("recent_auth_failures", 0)
    score -= min(60.0, fails * 15.0)
    return _clamp(score), reasons


def _score_device(device_flags: dict[str, Any]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    status = device_flags.get("status")
    if status == "revoked":
        return 0.0, ["DEVICE_REVOKED"]
    if status in ("unknown", "new") or device_flags.get("novel"):
        return 45.0, ["NEW_DEVICE"]
    if status == "active":
        return 100.0, ["KNOWN_DEVICE"]
    return 50.0, ["NO_DEVICE_TRACKING"]


def _score_behaviour(behaviour_flags: dict[str, Any], ml_signal: float | None) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 100.0
    rpm = behaviour_flags.get("requests_per_minute", 0.0)
    if rpm >= 120:
        score -= 60.0
        reasons.append("REQUEST_VELOCITY_EXCESSIVE")
    elif rpm >= 40:
        score -= 35.0
        reasons.append("REQUEST_VELOCITY_HIGH")
    if ml_signal is not None and ml_signal < -0.3:
        score -= 45.0
        reasons.append("ANOMALY_DETECTED")
    return _clamp(score), reasons


def _score_context(context_flags: dict[str, Any]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 100.0
    hour = context_flags.get("hour")
    if hour is not None and (hour < 6 or hour > 22):
        score -= 25.0
        reasons.append("UNUSUAL_HOUR")
    score -= min(30.0, context_flags.get("geo_penalty", 0.0))
    return _clamp(score), reasons


def _score_history(history_flags: dict[str, Any]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 100.0
    anomalies = history_flags.get("recent_anomalies", 0)
    if anomalies > 3:
        score -= 50.0
        reasons.append("HISTORY_ANOMALOUS")
    else:
        reasons.append("HISTORY_NORMAL")
    return _clamp(score), reasons


def evaluate_trust(context: dict[str, Any]) -> TrustState:
    """Compute an explainable trust state from a flattened context dict."""
    identity_s, id_reasons = _score_identity(context.get("identity", {}))
    device_s, dev_reasons = _score_device(context.get("device", {}))
    ml_signal = context.get("ml_signal")
    behaviour_s, beh_reasons = _score_behaviour(context.get("behaviour", {}), ml_signal)
    context_s, ctx_reasons = _score_context(context.get("context", {}))
    history_s, hist_reasons = _score_history(context.get("history", {}))

    components = {
        "identity": round(identity_s, 1),
        "device": round(device_s, 1),
        "behaviour": round(behaviour_s, 1),
        "context": round(context_s, 1),
        "history": round(history_s, 1),
    }
    score = (
        WEIGHTS["identity"] * identity_s
        + WEIGHTS["device"] * device_s
        + WEIGHTS["behaviour"] * behaviour_s
        + WEIGHTS["context"] * context_s
        + WEIGHTS["history"] * history_s
    )
    score = int(round(_clamp(score)))

    reasons = id_reasons + dev_reasons + beh_reasons + ctx_reasons + hist_reasons

    # Hard blocks are authoritative and independent of the numeric score.
    hard = None
    for code in ("CREDENTIAL_REVOKED", "DEVICE_REVOKED"):
        if code in reasons:
            hard = code
            break

    if hard:
        decision = "DENY"
    elif score >= ALLOW_THRESHOLD:
        decision = "ALLOW"
    elif score >= STEP_UP_THRESHOLD:
        decision = "STEP_UP"
    else:
        decision = "DENY"

    # Rule layer: reason codes can override the numeric band. This is what makes
    # an otherwise-clean user STEP_UP on a brand-new device or a velocity burst.
    # Rules may only downgrade a decision, never upgrade it.
    if decision == "ALLOW":
        if "REQUEST_VELOCITY_EXCESSIVE" in reasons:
            decision = "DENY"  # excessive burst is a hard-ish signal
        elif {
            "NEW_DEVICE",
            "REQUEST_VELOCITY_HIGH",
            "ANOMALY_DETECTED",
        }.intersection(reasons):
            decision = "STEP_UP"

    # AI/ML restriction is strictly downward-only. There is NO branch that lets
    # a negative ML signal move a decision toward a higher-privilege state.
    if ml_signal is not None and ml_signal < ML_BLOCK_THRESHOLD:
        decision = "DENY"
    elif ml_signal is not None and ml_signal < ML_RESTRICT_THRESHOLD:
        # Moderate anomaly: at most RESTRICTED (read-only / limited scope).
        if decision in ("ALLOW", "STEP_UP"):
            decision = "RESTRICTED"

    return TrustState(
        trust_score=score,
        decision=decision,
        reasons=reasons,
        components=components,
        ml_signal=ml_signal,
        hard_block=hard,
    )