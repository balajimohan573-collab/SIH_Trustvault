"""Test browser refresh & server restart persistence (real flows only).

Runs against the real dev database. No /auth/login/dev.

Run from backend/ :  .venv\\Scripts\\python.exe test_refresh_persistence.py
"""
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, SessionLocal, engine
from app.models import Credential, User

PASSWORD = "RefreshTestPass123!"
ADMIN_EMAIL = "admin@trustvault.example"


def _ensure_admin():
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
            # Dev tool: keep the admin usable regardless of who seeded the row.
            admin.role = "admin"
            admin.password_hash = hash_password(PASSWORD)
        db.commit()


def _ensure_user_password(email: str):
    from app.core.security import hash_password

    with SessionLocal() as db:
        u = db.query(User).filter(User.email == email).first()
        if u and not u.password_hash:
            u.password_hash = hash_password(PASSWORD)
            db.commit()


def run_test():
    _ensure_admin()
    print("=== TESTING REFRESH & PERSISTENCE ===")

    with TestClient(app) as client:
        # 1. Login (may need to register first)
        _ensure_user_password(ADMIN_EMAIL)
        r = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
        if r.status_code == 401:
            client.post(
                "/auth/register",
                json={"email": "balaji@trustvault.example", "password": PASSWORD, "full_name": "Balaji"},
            )
            r = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        user_id = r.json()["user"]["id"]

        # 2. Create Credential (admin = verified issuer)
        create_resp = client.post(
            "/credentials/issue",
            headers=headers,
            json={
                "holder_email": "balaji@trustvault.example",
                "type": "Master of Technology Certificate",
                "title": "Master of Technology Certificate",
                "claims": [
                    {"key": "name", "value": "Master of Technology Certificate", "public": True},
                    {"key": "issuer", "value": "IIT Madras", "public": True},
                    {"key": "issueDate", "value": "2026-06-01", "public": True},
                    {"key": "expiryDate", "value": "2036-06-01", "public": True},
                ],
            },
        )
        assert create_resp.status_code == 200, f"Issue failed: {create_resp.text}"
        cred = create_resp.json()
        cred_id = cred["id"]
        print(f"[OK] Credential created: id={cred_id}")

        # 3. Simulate browser refresh (new request / new DB Session)
        with SessionLocal() as db:
            c = db.get(Credential, cred_id)
            assert c is not None, "Credential DB record not found on fresh DB session!"
            assert c.type == "Master of Technology Certificate"
            assert c.issuer_name == "Platform Admin"
        print("[OK] Credential verified in fresh DB session after simulated restart")

        # 4. Fetch list via API (Simulates frontend mount after browser refresh)
        list_resp = client.get("/credentials?holder=me", headers=headers)
        assert list_resp.status_code == 200, list_resp.text
        match = [item for item in list_resp.json() if item["id"] == cred_id]
        assert len(match) == 1, "Credential missing after refresh!"
        assert match[0]["type"] == "Master of Technology Certificate"
        print("[OK] Credential retrieved via GET /credentials after simulated browser refresh")

    print("\nREFRESH PERSISTENCE TEST PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_test()