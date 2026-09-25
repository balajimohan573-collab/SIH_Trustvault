"""End-to-End Acceptance Test for TRUSTVAULT Backend & Database.

Runs against the real dev database (backend/.env DATABASE_URL). Uses ONLY real
flows: password register/login, DB-backed sessions, structured claims, verified
issuer/admin issuance, server-enforced IDOR checks, revocation persistence,
asset-based access grants with revocation, and real trust-engine reads.

No /auth/login/dev, no demo seeding, no fabricated hashes.

Run from backend/ :  .venv\\Scripts\\python.exe test_e2e_acceptance.py
"""
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, SessionLocal, engine
from app.models import Credential, User

PASSWORD = "AcceptancePass123!"
ADMIN_EMAIL = "admin@trustvault.example"


def _seed_admin_role():
    """Ensure an admin row exists (role is not self-registrable via the API)."""
    Base.metadata.create_all(bind=engine)
    from app.core.security import hash_password

    with SessionLocal() as db:
        admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if admin is None:
            admin = User(
                email=ADMIN_EMAIL,
                full_name="Platform Admin",
                password_hash=hash_password(PASSWORD),
                role="admin",
                did="did:trustvault:admin",
            )
            db.add(admin)
        else:
            admin.role = "admin"
            if not admin.password_hash:
                admin.password_hash = hash_password(PASSWORD)
        db.commit()


def _ensure_user_password(email: str):
    """Pre-refactor dev rows may lack a password_hash; set one so real login works."""
    from app.core.security import hash_password

    with SessionLocal() as db:
        u = db.query(User).filter(User.email == email).first()
        if u and not u.password_hash:
            u.password_hash = hash_password(PASSWORD)
            db.commit()


def _login(client, email):
    _ensure_user_password(email)
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"Login failed for {email}: {r.text}"
    return r.json()


def _register(client, email, name):
    r = client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": name},
    )
    # 409 = already registered; that is fine for repeat runs.
    assert r.status_code in (200, 409), f"Register failed for {email}: {r.text}"


def run_tests():
    _seed_admin_role()
    print("=== STARTING TRUSTVAULT E2E ACCEPTANCE TESTS ===")

    with TestClient(app) as client:
        # 1. Register real users + login
        _register(client, "balaji@trustvault.example", "Balaji")
        _register(client, "verifier@trustvault.example", "Verifier")
        holder = _login(client, "balaji@trustvault.example")
        verifier = _login(client, "verifier@trustvault.example")
        admin = _login(client, ADMIN_EMAIL)
        hh = {"Authorization": f"Bearer {holder['access_token']}"}
        hv = {"Authorization": f"Bearer {verifier['access_token']}"}
        ha = {"Authorization": f"Bearer {admin['access_token']}"}
        user_id = holder["user"]["id"]
        user_agent_headers = {**hh, "user-agent": "e2e-acceptance"}
        print(f"[OK] Registered + logged in as balaji@trustvault.example (user_id={user_id})")

        # 2. Admin (real verified issuer) issues a credential with structured claims
        create_resp = client.post(
            "/credentials/issue",
            headers=ha,
            json={
                "holder_email": "balaji@trustvault.example",
                "type": "Bachelor of Engineering Certificate",
                "title": "Bachelor of Engineering Certificate",
                "external_id": "SSE-2026-BE-E2E-TEST",
                "claims": [
                    {"key": "name", "value": "Bachelor of Engineering Certificate", "public": True},
                    {"key": "issuer", "value": "Saveetha School of Engineering", "public": True},
                    {"key": "issueDate", "value": "2026-05-15", "public": True},
                    {"key": "expiryDate", "value": "2036-05-15", "public": True},
                ],
            },
        )
        assert create_resp.status_code == 200, f"Create credential failed: {create_resp.text}"
        cred = create_resp.json()
        cred_id = cred["id"]
        print(f"[OK] Credential issued via API: id={cred_id}, hash={cred['hash'][:16]}...")

        # Verifier needs an active identity credential to pass the policy gate.
        vcred = client.post(
            "/credentials/issue",
            headers=ha,
            json={
                "holder_email": "verifier@trustvault.example",
                "type": "labour_department_id",
                "title": "Labour Department Officer ID",
                "claims": [
                    {"key": "full_name", "value": "Verifier", "public": True},
                    {"key": "department", "value": "Labour", "public": True},
                ],
            },
        )
        assert vcred.status_code == 200, f"Verifier credential failed: {vcred.text}"

        # 3. Verify DB Row & Persistence
        with SessionLocal() as db:
            db_cred = db.get(Credential, cred_id)
            assert db_cred is not None, "Credential DB row not found!"
            assert db_cred.holder_id == user_id, "Holder ID mismatch!"
            assert db_cred.status == "active", "Credential status is not active!"
            assert db_cred.issuer_name == "Platform Admin", "Issuer name mismatch!"
        print("[OK] DB Row verified in database")

        # 4. Get List of Credentials
        list_resp = client.get("/credentials?holder=me", headers=user_agent_headers)
        assert list_resp.status_code == 200, f"List credentials failed: {list_resp.text}"
        assert any(c["id"] == cred_id for c in list_resp.json()), "Created credential missing in list!"
        print("[OK] GET /credentials returned the created credential")

        # 5. Test IDOR Protection (another user must never read it)
        idor_resp = client.get(f"/credentials/{cred_id}", headers=hv)
        assert idor_resp.status_code == 403, f"IDOR check failed! Expected 403, got {idor_resp.status_code}"
        print("[OK] IDOR Protection verified: unauthorized user rejected with 403 Forbidden")

        # 6. Public verification endpoint works for the opaque token
        tok = db_cred.api_verification_token
        pub = client.get(f"/verify/{tok}")
        assert pub.status_code == 200, f"Public verify failed: {pub.text}"
        assert pub.json()["result"] == "VERIFIED", pub.text
        print("[OK] Public /verify/<token> reports VERIFIED for the issued credential")

        # 7. Revoke Credential (by its issuer)
        revoke_resp = client.post(
            f"/credentials/{cred_id}/revoke", headers=ha, json={"reason": "Test revoke"}
        )
        assert revoke_resp.status_code == 200, f"Revoke failed: {revoke_resp.text}"
        assert revoke_resp.json()["status"] == "revoked", "Status not revoked!"
        pub_after = client.get(f"/verify/{tok}").json()
        assert pub_after["result"] in ("REVOKED", "INVALID"), pub_after["result"]
        print("[OK] Credential revoked via API and public verify reflects it")

        # 8. Verify Revocation Persistence Across Query
        get_revoked = client.get(f"/credentials/{cred_id}", headers=user_agent_headers)
        assert get_revoked.status_code == 200, get_revoked.text
        assert get_revoked.json()["status"] == "revoked", "Revoked status failed to persist!"
        print("[OK] Revoked status persisted in database across requests")

        # 9. Asset-based Access Grant & Revocation
        up = client.post(
            "/assets", headers=user_agent_headers,
            files={"file": ("employment-report.pdf", b"EMPLOYMENT REPORT", "application/pdf")},
        )
        assert up.status_code == 200, f"Asset upload failed: {up.text}"
        asset_id = up.json()["id"]

        pol = client.post(
            f"/assets/{asset_id}/policy",
            headers=user_agent_headers,
            json={"requester_role": "holder", "purpose": "Employment Verification", "min_trust": 0},
        )
        assert pol.status_code == 200, f"Policy create failed: {pol.text}"

        req = client.post(
            "/access/request",
            headers=hv,
            json={"asset_id": asset_id, "purpose": "Employment Verification"},
        )
        assert req.status_code == 200, f"Access request failed: {req.text}"
        req_id = req.json()["id"]
        grant = client.post(
            f"/access/{req_id}/approve",
            headers=user_agent_headers,
            json={"decision": "approve", "duration_minutes": 60},
        )
        assert grant.status_code == 200, f"Grant failed: {grant.text}"
        grant_id = grant.json()["id"]

        content = client.get(f"/assets/{asset_id}/content", headers=hv)
        assert content.status_code == 200, f"Granted content read failed: {content.text}"
        assert b"EMPLOYMENT REPORT" in content.content
        print("[OK] Scoped access grant works (request -> approve -> decrypt on read)")

        revoke_grant = client.post(f"/access/grants/{grant_id}/revoke", headers=user_agent_headers)
        assert revoke_grant.status_code == 200, f"Revoke grant failed: {revoke_grant.text}"
        blocked = client.get(f"/assets/{asset_id}/content", headers=hv)
        assert blocked.status_code == 403, f"Revoked grant still readable! {blocked.status_code}"
        print("[OK] Access grant revoked and immediately enforced")

        # 10. Trust Engine real read (live state, never simulated)
        trust = client.get(f"/trust/{user_id}", headers=user_agent_headers)
        assert trust.status_code == 200, f"Trust read failed: {trust.text}"
        body = trust.json()
        assert "trust_score" in body, "Trust endpoint must return a real live score"
        print(f"[OK] Trust Engine live read: score={body['trust_score']} decision={body['decision']}")

    print("\nALL ACCEPTANCE TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_tests()