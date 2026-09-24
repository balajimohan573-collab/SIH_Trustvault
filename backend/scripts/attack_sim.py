"""TrustVault attack simulation - replay the threat journey end-to-end.

Requires the backend running with seeded users:

    cd backend
    $env:RATE_LIMIT_MAX = "500"
    .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000

Scenarios (each ends with a PASS/FAIL verdict):

    A  Forged / tampered JWT            -> 401, no data leak
    B  IDOR / no-permission attempt     -> DENY NO_POLICY_FOR_ROLE (403)
    C  Scoped, time-bound grant          -> verifier download ALLOW (baseline)
    C2 Context-aware policy (location)   -> RESTRICTED when context is missing/mismatched,
                                           ALLOW when the declared context matches
    D  Attack becomes visible           -> velocity + auth-failure storm
                                          drags trust down, clean download
                                          collapses ALLOW -> STEP_UP
    F  Admin override recovery          -> ALLOW, privileged entry + anchor
    E  Instantly-propagating revocation -> DENY CREDENTIAL_REVOKED
    G  Audit trail                       -> high-value events anchored
    H  Duress freeze (optional)         -> when enabled, holder's sensitive access is DENY
"""
import time
import uuid

import httpx

BASE = "http://localhost:8000"
PASS, FAIL = 0, 0


def banner(text):
    print("\n" + "=" * 66)
    print("  " + text)
    print("=" * 66)


def verdict(ok, what):
    global PASS, FAIL
    PASS += 1 if ok else 0
    FAIL += 0 if ok else 1
    print(f"[{' PASS ' if ok else ' FAIL '}] {what}")


class Sim:
    def __init__(self):
        self.client = httpx.Client(timeout=30.0, base_url=BASE)
        self.tokens = {}

    def call(self, method, path, headers=None, **kw):
        """HTTP helper that survives the rate limiter (429 -> cool-down + retry)."""
        for attempt in (1, 2):
            r = self.client.request(method, path, headers=headers or {}, **kw)
            if r.status_code == 429 and attempt == 1:
                print("   (rate-limited, cooling down 62s ...)")
                time.sleep(62)
                continue
            return r
        return r

    def login(self, label, email):
        r = self.call("POST", "/auth/login/dev", json={"email": email})
        assert r.status_code == 200, f"{label} login failed: {r.text[:200]}"
        self.tokens[label] = r.json()["access_token"]
        return r.json()["user"]

    def auth(self, label, **headers):
        h = {"Authorization": f"Bearer {self.tokens[label]}"}
        h.update(headers)
        return h

    def post_security(self, label, event_type, user_id=None, **signals):
        body = {"event_type": event_type, "risk_signals": signals or {}}
        if user_id:
            body["user_id"] = user_id
        return self.call("POST", "/security/events", headers=self.auth(label), json=body)

    def trust(self, label, user_id):
        r = self.call("GET", f"/trust/{user_id}", headers=self.auth(label))
        return r.json() if r.status_code == 200 else None

    def download(self, label, asset_id, **headers):
        return self.call("GET", f"/assets/{asset_id}/content", headers=self.auth(label, **headers))


def grant_flow(sim, requester_label, owner_label, asset_id, purpose, duration=30):
    """requester asks, owner approves -> active scoped grant."""
    r = sim.call(
        "POST", "/access/request", headers=sim.auth(requester_label),
        json={"asset_id": asset_id, "purpose": purpose},
    )
    assert r.status_code in (200, 403), f"access request failed: {r.text[:200]}"
    if r.status_code != 200:
        return None
    request_id = r.json()["id"]
    r = sim.call(
        "POST", f"/access/{request_id}/approve", headers=sim.auth(owner_label),
        json={"decision": "approve", "duration_minutes": duration},
    )
    assert r.status_code == 200, f"approve failed: {r.text[:200]}"
    return r.json()


def main():
    sim = Sim()

    # ---------- Phase 0: bootstrap ----------
    banner("BOOTSTRAP - seeded roles + encrypted assets + credentials")
    admin = sim.login("admin", "admin@trustvault.example")
    issuer = sim.login("issuer", "issuer@trustvault.example")
    holder = sim.login("holder", "holder@trustvault.example")
    verifier = sim.login("verifier", "verifier@trustvault.example")
    holder_id, verifier_id = holder["id"], verifier["id"]

    for email, who in [("holder@trustvault.example", "holder"), ("verifier@trustvault.example", "verifier")]:
        r = sim.call(
            "POST", "/credentials/issue", headers=sim.auth("issuer"),
            json={"holder_email": email, "type": "education",
                  "document": {"institution": "Demo University", "degree": "B.Sc."}},
        )
        assert r.status_code == 200, f"credential issue failed: {r.text[:200]}"
        if who == "verifier":
            verifier_cred_id = r.json()["id"]
    print("  credentials issued (only SHA-256 hashes stored, never raw docs)")

    files = {"file": ("fincrisis-response-plan.pdf", b"TOP SECRET " + uuid.uuid4().bytes, "application/pdf")}
    r = sim.call("POST", "/assets", headers=sim.auth("holder"), files=files)
    assert r.status_code == 200, f"asset upload failed: {r.text[:200]}"
    asset = r.json()

    decoy = {"file": ("encryption-keys-decoy.pdf", b"DECOY " + uuid.uuid4().bytes, "application/pdf")}
    r = sim.call("POST", "/assets", headers=sim.auth("holder"), files=decoy)
    assert r.status_code == 200, f"decoy upload failed: {r.text[:200]}"
    decoy_asset = r.json()

    # Scope a purpose (ABAC) for the verifier on the real asset.
    r = sim.call(
        "POST", f"/assets/{asset['id']}/policy", headers=sim.auth("holder"),
        json={"requester_role": "verifier", "purpose": "employment", "min_trust": 60},
    )
    assert r.status_code == 200, f"policy create failed: {r.text[:200]}"
    print(f"  holder uploaded 2 assets; scoped a verifier/employment policy (min_trust 60)")

    # ---------- A: forged JWT ----------
    banner("A - ATTACK SURFACE: forged / tampered JWT")
    r = sim.call("GET", "/auth/me", headers={"Authorization": "Bearer eyJh.GARBAGE.zzz"})
    verdict(r.status_code in (401, 403), f"forged JWT rejected with {r.status_code}")
    print("  Reason: JWT signature verification happens before any business logic runs.")

    # ---------- B: IDOR / privilege escalation ----------
    banner("B - ATTACK: horizontal escalation (verifier grabs a decoy asset)")
    r = sim.download("verifier", decoy_asset["id"])
    reasons = (r.json().get("detail") or {}).get("reasons", []) if r.status_code == 403 else []
    verdict(r.status_code == 403 and "NO_POLICY_FOR_ROLE" in reasons,
            f"verifier download without policy/grant -> 403 DENY {reasons}")
    r = sim.download("verifier", decoy_asset["id"], **{"X-TrustVault-Admin-Override": "1"})
    verdict(r.status_code == 403, "non-admin override header is ignored (still DENY)")

    # ---------- C: legitimate scoped grant ----------
    banner("C - BASELINE: owner grants purpose-scoped, time-bound access")
    grant = grant_flow(sim, "verifier", "holder", asset["id"], "employment")
    assert grant is not None, "grant flow failed"
    print(f"  grant {grant['id'][:8]}... purpose={grant['purpose']} expires={grant['expires_at']}")
    r = sim.download("verifier", asset["id"])
    ok = r.status_code == 200 and b"TOP SECRET" in r.content
    verdict(ok, f"granted verifier download -> ALLOW, content served ({len(r.content)} bytes)")
    t0 = sim.trust("verifier", verifier_id)
    if t0:
        print(f"  trust baseline: score={t0['trust_score']} decision={t0['decision']} reasons={t0['reasons']}")

    # ---------- C2: context-aware policy (location) ----------
    banner("C2 - CONTEXT: declared location degrades to RESTRICTED, never DENY, when missing")
    r = sim.call(
        "POST", f"/assets/{asset['id']}/policy", headers=sim.auth("holder"),
        json={"requester_role": "verifier", "purpose": "audit", "min_trust": 50,
              "location_scope": "HQ-Floor-3", "location_strict": False},
    )
    assert r.status_code == 200, f"audit policy create failed: {r.text[:200]}"
    grant_flow(sim, "verifier", "holder", asset["id"], "audit")
    r = sim.download("verifier", asset["id"])
    if r.status_code == 403:
        detail = r.json().get("detail") or {}
        reasons = detail.get("reasons", [])
        verdict(detail.get("decision") == "RESTRICTED" and "LOCATION_MISSING" in reasons,
                f"no location context -> RESTRICTED {reasons}")
    else:
        verdict(False, "no location context -> expected RESTRICTED, got " + str(r.status_code))
    r = sim.download("verifier", asset["id"], **{"X-TrustVault-Location-Scope": "HQ-Floor-2"})
    if r.status_code == 403:
        detail = r.json().get("detail") or {}
        reasons = detail.get("reasons", [])
        verdict(detail.get("decision") == "RESTRICTED" and "LOCATION_MISMATCH" in reasons,
                f"wrong location -> RESTRICTED {reasons}")
    else:
        verdict(False, "wrong location -> expected RESTRICTED, got " + str(r.status_code))
    r = sim.download("verifier", asset["id"], **{"X-TrustVault-Location-Scope": "HQ-Floor-3"})
    verdict(r.status_code == 200 and b"TOP SECRET" in r.content,
            f"matching location context -> ALLOW ({len(r.content)} bytes)")

    # ---------- H: duress freeze (feature-flagged) ----------
    banner("H - DURESS: covert freeze of sensitive access (default disabled)")
    r = sim.call("POST", "/duress/activate", headers=sim.auth("verifier"))
    if r.status_code == 400:
        print("  duress module disabled by default - start backend with "
              "DURESS_ENABLED=true and re-run to exercise the hide-in-plain-sight freeze")
        verdict(True, "duress feature-flagged off, endpoint responds 400")
    else:
        assert r.status_code == 200, f"duress activate failed: {r.text[:200]}"
        status = sim.call("GET", "/duress/status", headers=sim.auth("verifier")).json()
        print(f"  verifier declared duress; active={status['active']}, "
              f"trust surface looks normal (hide-in-plain-sight)")
        r = sim.download("verifier", asset["id"], **{"X-TrustVault-Location-Scope": "HQ-Floor-3"})
        reasons = (r.json().get("detail") or {}).get("reasons", []) if r.status_code == 403 else []
        verdict(r.status_code == 403 and "DURESS_ACTIVE" in reasons,
                f"even a valid grant is frozen -> 403 DENY {reasons}")
        sim.call("POST", "/duress/deactivate", headers=sim.auth("verifier"))
        r = sim.download("verifier", asset["id"], **{"X-TrustVault-Location-Scope": "HQ-Floor-3"})
        verdict(r.status_code == 200, f"after PIN deactivation access restored ({r.status_code})")

    # ---------- D: attack becomes visible ----------
    banner("D - ATTACK: request-storm + auth-failure burst (attacker impersonates verifier)")
    for _ in range(40):
        sim.post_security("verifier", "access_attempted", user_id=verifier_id, asset_id=asset["id"])
    for _ in range(4):
        sim.post_security("verifier", "auth_failed", user_id=verifier_id, source="scraped-password")
    time.sleep(1)
    t1 = sim.trust("verifier", verifier_id)
    if t1:
        print(f"  trust during attack: score={t1['trust_score']} decision={t1['decision']}")
    r = sim.download("verifier", asset["id"], **{"X-TrustVault-Location-Scope": "HQ-Floor-3"})
    detail = (r.json().get("detail") or {}) if r.status_code == 403 else {}
    reasons = detail.get("reasons", [])
    ok = r.status_code == 403 and detail.get("decision") == "STEP_UP"
    verdict(ok, f"clean download forced to STEP_UP {tuple(reasons)} ")
    if t0 and t1:
        print(f"  score delta: {t0['trust_score']} -> {t1['trust_score']} "
              f"(identity penalty + velocity burst)")

    # ---------- F: admin override ----------
    banner("F - RECOVERY: admin override (documented, privileged, auditable)")
    r = sim.download("admin", asset["id"], **{"X-TrustVault-Admin-Override": "1"})
    verdict(r.status_code == 200, "admin override ALLOWs and returns content")
    ev = sim.call("GET", "/security/events", headers=sim.auth("admin")).json()
    override_evt = next((e for e in ev if "ADMIN_OVERRIDE" in str(e.get("risk_signals", {}))), None)
    verdict(bool(override_evt), "override added privileged audit entry + anchor")

    # ---------- E: revocation ----------
    banner("E - ATTACK RESPONSE: credential revocation propagates instantly")
    r = sim.call("POST", f"/credentials/{verifier_cred_id}/revoke", headers=sim.auth("issuer"),
                 json={"reason": "suspected compromise"})
    assert r.status_code == 200, f"revoke failed: {r.text[:200]}"
    print("  issuer revoked the verifier credential")
    r = sim.download("verifier", asset["id"])
    detail = (r.json().get("detail") or {}) if r.status_code == 403 else {}
    reasons = detail.get("reasons", [])
    verdict(r.status_code == 403 and "CREDENTIAL_REVOKED" in reasons,
            f"verifier download hard-blocked {reasons}")

    # ---------- G: audit trail ----------
    banner("G - AUDIT: every high-value event anchored (tx pending / on-chain)")
    anchored = 0
    for aid, what in ((asset["id"], "primary asset"),):
        r = sim.call("GET", f"/audit/{aid}", headers=sim.auth("admin"))
        rows = r.json() if r.status_code == 200 else []
        anchored = sum(1 for row in rows if row.get("anchor"))
        print(f"  audit trail for {what}: {len(rows)} events, {anchored} with on-chain anchor rows")
        for row in rows:
            anchor = row.get("anchor")
            if anchor:
                print(f"   - {row['event_type']:<18} trust={row.get('trust_score')} "
                      f"{anchor.get('chain')} [{anchor.get('status')}] {anchor.get('tx_hash', '')[:12] or ''}")
    verdict(anchored >= 3, "asset_created + access_allowed + access_blocked anchored")

    print("\n" + "=" * 66)
    print(f" SUMMARY: {PASS} passed, {FAIL} failed")
    print("=" * 66)
    if FAIL:
        raise SystemExit(1)


if __name__ == "__main__":
    main()