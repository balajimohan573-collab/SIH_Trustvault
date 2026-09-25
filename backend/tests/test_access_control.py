"""Access-control pipeline tests for the 7 required scenarios:

 1. Valid credential + authorized role + normal context            -> ALLOW
 2. Valid credential + new device                                  -> STEP_UP
 3. Valid credential + expired grant                               -> DENY
 4. Revoked credential                                             -> DENY
 5. Authorized role but wrong purpose                               -> DENY
 6. Suspicious velocity but otherwise valid                         -> STEP_UP or DENY per policy
 7. Admin override                                                  -> ALLOW with privileged audit trail
"""
from datetime import datetime, timedelta

from app.db.session import SessionLocal
from app.models import Credential, TrustedDevice


def _latest_device_status(db, user_id: str) -> str:
    d = (
        db.query(TrustedDevice)
        .filter(TrustedDevice.user_id == user_id)
        .order_by(TrustedDevice.last_seen.desc())
        .first()
    )
    return d.status


# ---------------------------------------------------------------- Scenario 1
def test_valid_credential_authorized_role_allows(seeded_flow):
    f = seeded_flow
    req = f["request_access"]()
    f["approve"](req["id"])
    h = f["headers"]["verifier"]
    r = f["client"].get(f"/assets/{f['asset_id']}/content", headers=h)
    assert r.status_code == 200, r.text
    assert r.content == b"EMPLOYMENT REPORT"


# ---------------------------------------------------------------- Scenario 2
def test_new_device_steps_up(seeded_flow):
    f = seeded_flow
    req = f["request_access"]()
    f["approve"](req["id"])

    # Simulate a brand-new (never-seen) device: most recent device row is "new".
    verifier_id = f["headers"]["verifier"]
    with SessionLocal() as db:
        from app.models import User

        v = db.query(User).filter(User.email == "verifier@trustvault.example").first()
        db.add(
            TrustedDevice(
                user_id=v.id,
                device_key_id="unseen-yubikey-001",
                label="sneakernet",
                status="new",
                last_seen=datetime.utcnow() + timedelta(seconds=1),
            )
        )
        db.commit()

    r = f["client"].get(f"/assets/{f['asset_id']}/content", headers=verifier_id)
    assert r.status_code == 403
    body = r.json()["detail"]
    assert body["decision"] == "STEP_UP", body
    assert "NEW_DEVICE" in body["reasons"], body


# ---------------------------------------------------------------- Scenario 3
def test_expired_grant_denied(seeded_flow):
    f = seeded_flow
    req = f["request_access"]()
    f["approve"](req["id"], duration=30)

    # Backdate the grant so it is outside its validity window.
    with SessionLocal() as db:
        from app.models import AccessGrant

        g = db.query(AccessGrant).order_by(AccessGrant.granted_at.desc()).first()
        g.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.commit()

    r = f["client"].get(f"/assets/{f['asset_id']}/content", headers=f["headers"]["verifier"])
    assert r.status_code == 403
    assert r.json()["detail"]["decision"] == "DENY"
    assert "GRANT_EXPIRED" in r.json()["detail"]["reasons"]


# ---------------------------------------------------------------- Scenario 4
def test_revoked_credential_denied(seeded_flow):
    f = seeded_flow
    req = f["request_access"]()
    f["approve"](req["id"])

    # Revoke the verifier's credential.
    client = f["client"]
    # (f["credential_id"] belongs to the HOLDER; revoke verifier's credential.)
    with SessionLocal() as db:
        from app.models import Credential, User

        v = db.query(User).filter(User.email == "verifier@trustvault.example").first()
        vcred = db.query(Credential).filter(Credential.holder_id == v.id).first()
        vcred.status = "revoked"
        vcred.revoked_at = datetime.utcnow()
        db.commit()
        verifier_cred = vcred.id

    r = client.get(f"/assets/{f['asset_id']}/content", headers=f["headers"]["verifier"])
    assert r.status_code == 403
    assert r.json()["detail"]["decision"] == "DENY"
    assert "CREDENTIAL_REVOKED" in r.json()["detail"]["reasons"]
    assert verifier_cred


# ---------------------------------------------------------------- Scenario 5
def test_wrong_purpose_denied(seeded_flow):
    f = seeded_flow
    req = f["request_access"]()
    f["approve"](req["id"])

    # Try to access with a purpose that has no policy (and no grant purpose).
    with SessionLocal() as db:
        from app.models import AccessGrant

        g = db.query(AccessGrant).order_by(AccessGrant.granted_at.desc()).first()
        g.purpose = "medical"  # owner approved for employment; attacker claims medical
        db.commit()

    r = f["client"].get(f"/assets/{f['asset_id']}/content", headers=f["headers"]["verifier"])
    assert r.status_code == 403
    assert "WRONG_PURPOSE" in r.json()["detail"]["reasons"]


# ---------------------------------------------------------------- Scenario 6
def test_suspicious_velocity_steps_up(seeded_flow):
    f = seeded_flow
    req = f["request_access"]()
    f["approve"](req["id"])

    # Inject a burst of recent access events to inflate requests-per-minute.
    with SessionLocal() as db:
        from app.models import SecurityEvent, User

        v = db.query(User).filter(User.email == "verifier@trustvault.example").first()
        for _ in range(50):
            db.add(SecurityEvent(user_id=v.id, event_type="access", risk_signals={}))
        db.commit()

    r = f["client"].get(f"/assets/{f['asset_id']}/content", headers=f["headers"]["verifier"])
    assert r.status_code == 403
    body = r.json()["detail"]
    # thresholds: rpm>=120 -> DENY, rpm>=40 -> STEP_UP (50 events -> high velocity)
    assert "REQUEST_VELOCITY_HIGH" in body["reasons"], body
    assert body["decision"] in ("STEP_UP", "DENY")


def test_suspicious_velocity_excessive_denies_per_policy(seeded_flow):
    f = seeded_flow
    req = f["request_access"]()
    f["approve"](req["id"])

    with SessionLocal() as db:
        from app.models import SecurityEvent, User

        v = db.query(User).filter(User.email == "verifier@trustvault.example").first()
        for _ in range(150):
            db.add(SecurityEvent(user_id=v.id, event_type="access", risk_signals={}))
        db.commit()

    r = f["client"].get(f"/assets/{f['asset_id']}/content", headers=f["headers"]["verifier"])
    assert r.status_code == 403
    assert "REQUEST_VELOCITY_EXCESSIVE" in r.json()["detail"]["reasons"]
    assert r.json()["detail"]["decision"] == "DENY"


# ---------------------------------------------------------------- Scenario 7
def test_admin_override_allows_with_privileged_audit(seeded_flow):
    f = seeded_flow
    # No grant, no matching role policy path — but admin override forces ALLOW.
    h = f["headers"]["admin"]
    r = f["client"].get(
        f"/assets/{f['asset_id']}/content",
        headers={**h, "X-TrustVault-Admin-Override": "1"},
    )
    assert r.status_code == 200, r.text
    assert r.content == b"EMPLOYMENT REPORT"

    # The override MUST leave a privileged audit trail entry.
    events = f["client"].get(f"/audit/{f['asset_id']}", headers=h)
    events.raise_for_status()
    bodies = [e["risk_signals"] for e in events.json()]
    privileged = [b for b in bodies if b.get("privileged")]
    assert privileged, "No privileged audit trail entry found"
    reason_lists = [b.get("reasons", []) for b in privileged]
    assert any("ADMIN_OVERRIDE" in r2 for r2 in reason_lists)


def test_admin_override_ignored_for_non_admin(seeded_flow):
    f = seeded_flow
    # Non-admin must NOT be able to force ALLOW.
    r = f["client"].get(
        f"/assets/{f['asset_id']}/content",
        headers={**f["headers"]["verifier"], "X-TrustVault-Admin-Override": "1"},
    )
    assert r.status_code == 403
    assert "ADMIN_OVERRIDE" not in r.json()["detail"]["reasons"]


# ---------------------------------------------------------------- V2: location policy (optional, policy-based)
def _set_location_policy(location_scope, strict):
    with SessionLocal() as db:
        from app.models import AccessPolicy

        p = db.query(AccessPolicy).filter(AccessPolicy.purpose == "employment").first()
        p.location_scope = location_scope
        p.location_strict = strict
        db.commit()


def test_location_policy_missing_context_is_read_only(seeded_flow):
    f = seeded_flow
    _set_location_policy("nellai_office", strict=False)
    req = f["request_access"]()  # pre-flight: RESTRICTED is not DENY -> request created
    f["approve"](req["id"])

    r = f["client"].get(f"/assets/{f['asset_id']}/content", headers=f["headers"]["verifier"])
    assert r.status_code == 403, r.text
    detail = r.json()["detail"]
    assert detail["decision"] == "RESTRICTED", detail
    assert detail["scope"] == "read-only", detail
    assert "LOCATION_MISSING" in detail["reasons"], detail
    # Human-friendly decision layer present for the UI.
    assert detail.get("human"), detail
    assert detail.get("next_action"), detail


def test_location_policy_strict_mismatch_denies(seeded_flow):
    f = seeded_flow
    req = f["request_access"]()
    f["approve"](req["id"])
    _set_location_policy("nellai_office", strict=True)

    r = f["client"].get(f"/assets/{f['asset_id']}/content", headers=f["headers"]["verifier"])
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["decision"] == "DENY", detail
    assert "LOCATION_MISSING" in detail["reasons"] or "LOCATION_MISMATCH" in detail["reasons"]


def test_location_policy_matching_header_allows(seeded_flow):
    f = seeded_flow
    req = f["request_access"]()
    f["approve"](req["id"])
    _set_location_policy("nellai_office", strict=True)

    r = f["client"].get(
        f"/assets/{f['asset_id']}/content",
        headers={
            **f["headers"]["verifier"],
            "X-TrustVault-Location-Scope": "nellai_office",
        },
    )
    assert r.status_code == 200, r.text
    assert r.content == b"EMPLOYMENT REPORT"


# ---------------------------------------------------------------- V2: AI may only restrict (never grant)
def test_ml_signal_never_grants():
    from app.services.trust import evaluate_trust

    def ctx(ml):
        return {
            "identity": {"has_active_credential": True, "credential_revoked": False, "recent_auth_failures": 0},
            "device": {"status": "active", "novel": False},
            "behaviour": {"requests_per_minute": 0, "access_sequence": None},
            "context": {"hour": 12, "geo_penalty": 0.0},
            "history": {"recent_anomalies": 0},
            "ml_signal": ml,
        }

    # Strong anomaly -> DENY even with a perfect 100 score.
    assert evaluate_trust(ctx(-0.7)).decision == "DENY"
    # Moderate anomaly -> at most RESTRICTED (never ALLOW).
    moderate = evaluate_trust(ctx(-0.4))
    assert moderate.decision in ("RESTRICTED", "DENY")
    assert moderate.decision != "ALLOW"
    # Clean context with no ML -> ALLOW.
    assert evaluate_trust(ctx(None)).decision == "ALLOW"