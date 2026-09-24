import os
import tempfile

# Configure isolated test env BEFORE importing the app.
_TEST_DIR = tempfile.mkdtemp(prefix="trustvault_test_")
os.environ["DATABASE_URL"] = "sqlite://"  # in-memory, shared StaticPool
os.environ["STORAGE_DIR"] = f"{_TEST_DIR}/storage"
os.environ["ML_ANOMALY_ENABLED"] = "false"
os.environ["RATE_LIMIT_MAX"] = "100000"  # tests make many rapid requests

import pytest
from fastapi.testclient import TestClient

from app.db.session import Base, SessionLocal, engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _clean_db():
    from app.models import (
        AccessGrant,
        AccessPolicy,
        AccessRequest,
        Asset,
        AssetTransfer,
        AuditAnchor,
        Credential,
        Device,
        DeviceRecovery,
        DuressSession,
        OfflineEvent,
        SecurityEvent,
        User,
        WebAuthnCredential,
    )

    session = SessionLocal()
    try:
        for model in reversed(
            [
                AssetTransfer,
                OfflineEvent,
                DeviceRecovery,
                DuressSession,
                WebAuthnCredential,
                Device,
                AuditAnchor,
                SecurityEvent,
                AccessGrant,
                AccessRequest,
                AccessPolicy,
                Credential,
                Asset,
                User,
            ]
        ):
            session.query(model).delete()
        session.commit()
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _clean_per_test():
    _clean_db()
    yield
    _clean_db()


@pytest.fixture
def dev_login(client):
    def _login(email: str) -> str:
        r = client.post("/auth/login/dev", json={"email": email})
        assert r.status_code == 200, r.text
        return r.json()["access_token"]

    return _login


@pytest.fixture
def seed_users(db):
    from app.models import User

    users = {
        role: User(email=f"{role}@trustvault.example", did=f"did:trustvault:{role}", role=role)
        for role in ("holder", "issuer", "verifier", "admin")
    }
    db.add_all(users.values())
    db.commit()
    for u in users.values():
        db.refresh(u)
    return users


@pytest.fixture
def seeded_flow(client, seed_users, dev_login):
    """Full happy-path world: credential issued, asset uploaded, policy created."""
    tok_holder = dev_login("holder@trustvault.example")
    tok_issuer = dev_login("issuer@trustvault.example")
    tok_verifier = dev_login("verifier@trustvault.example")
    tok_admin = dev_login("admin@trustvault.example")
    h_holder = {"Authorization": f"Bearer {tok_holder}"}
    h_issuer = {"Authorization": f"Bearer {tok_issuer}"}
    h_verifier = {"Authorization": f"Bearer {tok_verifier}"}
    h_admin = {"Authorization": f"Bearer {tok_admin}"}

    # Issuer issues a credential to the holder.
    cred = client.post(
        "/credentials/issue",
        headers=h_issuer,
        json={
            "holder_email": "holder@trustvault.example",
            "type": "employment_verification",
            "document": {"degree": "BSc", "university": "IIT"},
        },
    )
    assert cred.status_code == 200, cred.text
    # Verifier holds an identity credential too (so step 2 passes for them).
    client.post(
        "/credentials/issue",
        headers=h_issuer,
        json={
            "holder_email": "verifier@trustvault.example",
            "type": "verifier_license",
            "document": {"org": "HR Bureau"},
        },
    )

    # Holder uploads an asset (employment report).
    upl = client.post(
        "/assets", headers=h_holder, files={"file": ("report.pdf", b"EMPLOYMENT REPORT", "application/pdf")}
    )
    assert upl.status_code == 200, upl.text
    asset_id = upl.json()["id"]

    # Holder defines a policy for verifiers, purpose=employment, min trust 50.
    pol = client.post(
        f"/assets/{asset_id}/policy",
        headers=h_holder,
        json={"requester_role": "verifier", "purpose": "employment", "min_trust": 50},
    )
    assert pol.status_code == 200, pol.text

    def request_access():
        r = client.post(
            "/access/request",
            headers=h_verifier,
            json={"asset_id": asset_id, "purpose": "employment"},
        )
        assert r.status_code == 200, r.text
        return r.json()

    def approve(req_id, duration=30):
        r = client.post(
            f"/access/{req_id}/approve",
            headers=h_holder,
            json={"decision": "approve", "duration_minutes": duration},
        )
        assert r.status_code == 200, r.text
        return r.json()

    return {
        "asset_id": asset_id,
        "headers": {
            "holder": h_holder,
            "issuer": h_issuer,
            "verifier": h_verifier,
            "admin": h_admin,
        },
        "request_access": request_access,
        "approve": approve,
        "credential_id": cred.json()["id"],
        "client": client,
        "db": db if False else None,
    }