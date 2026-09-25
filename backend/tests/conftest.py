import os
import tempfile

# Configure isolated test env BEFORE importing the app.
_TEST_DIR = tempfile.mkdtemp(prefix="trustvault_test_")
os.environ["DATABASE_URL"] = "sqlite://"  # in-memory, shared StaticPool
os.environ["STORAGE_DIR"] = f"{_TEST_DIR}/storage"
os.environ["ML_ANOMALY_ENABLED"] = "false"
os.environ["RATE_LIMIT_MAX"] = "100000"  # tests make many rapid requests
os.environ["RESET_TOKEN_DEV_DELIVERY"] = "true"

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
        AuditEvent,
        Credential,
        CredentialAccessGrant,
        CredentialAccessRequest,
        CredentialClaim,
        CredentialFile,
        CredentialIssuer,
        DeviceRecovery,
        DuressSession,
        Notification,
        OfflineEvent,
        Organization,
        Revocation,
        SecurityEvent,
        Session,
        TrustedDevice,
        User,
        VerificationEvent,
        WebAuthnCredential,
    )

    session = SessionLocal()
    try:
        for model in reversed(
            [
                VerificationEvent,
                CredentialFile,
                CredentialClaim,
                CredentialIssuer,
                Revocation,
                CredentialAccessGrant,
                CredentialAccessRequest,
                Notification,
                AuditEvent,
                AuditAnchor,
                Session,
                SecurityEvent,
                TrustedDevice,
                WebAuthnCredential,
                OfflineEvent,
                DeviceRecovery,
                DuressSession,
                AssetTransfer,
                AccessGrant,
                AccessRequest,
                AccessPolicy,
                Revocation,
                Credential,
                Asset,
                Organization,
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


TEST_PASSWORD = "TestPassord123!"


def _seed_user(db, role: str):
    from app.core.security import hash_password
    from app.models import User

    user = User(
        email=f"{role}@trustvault.example",
        full_name=f"{role.title()} User",
        password_hash=hash_password(TEST_PASSWORD),
        role=role,
        did=f"did:trustvault:{role}",
    )
    db.add(user)
    return user


@pytest.fixture
def seed_users(db):
    from app.models import User

    users = {role: _seed_user(db, role) for role in ("holder", "issuer", "verifier", "admin")}
    db.commit()
    for u in users.values():
        db.refresh(u)
    return users


@pytest.fixture
def login(client):
    def _login(email: str) -> str:
        r = client.post(
            "/auth/login", json={"email": email, "password": TEST_PASSWORD}
        )
        assert r.status_code == 200, r.text
        return r.json()["access_token"]

    return _login


@pytest.fixture
def verify_issuer_org(client, seed_users, login):
    """Grant the seeded issuer a VERIFIED organization via the real API flow."""

    def _verify() -> str:
        issuer_token = login("issuer@trustvault.example")
        h_issuer = {"Authorization": f"Bearer {issuer_token}"}
        apply = client.post(
            "/organizations",
            headers=h_issuer,
            json={
                "name": "Test University",
                "official_domain": "testuniversity.example",
                "org_identifier": "UNI-TEST-01",
            },
        )
        assert apply.status_code == 200, apply.text
        org_id = apply.json()["id"]

        admin_token = login("admin@trustvault.example")
        decide = client.post(
            f"/organizations/{org_id}/decide",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"approve": True},
        )
        assert decide.status_code == 200, decide.text
        assert decide.json()["verification_status"] == "verified"
        return org_id

    return _verify


@pytest.fixture
def seeded_flow(client, seed_users, login, verify_issuer_org):
    """Real happy-path world: org verified, credential issued, asset + policy."""
    org_id = verify_issuer_org()

    headers = {
        role: {"Authorization": f"Bearer {login(f'{role}@trustvault.example')}"}
        for role in ("holder", "issuer", "verifier", "admin")
    }

    def _issue_credential(to_email: str, cred_type: str) -> str:
        r = client.post(
            "/credentials/issue",
            headers=headers["issuer"],
            json={
                "holder_email": to_email,
                "type": cred_type,
                "title": cred_type,
                "claims": [
                    {"key": "full_name", "value": to_email.split("@")[0], "public": True},
                    {"key": "institute", "value": "Test University", "public": True},
                ],
            },
        )
        assert r.status_code == 200, r.text
        return r.json()["id"]

    holder_cred = _issue_credential("holder@trustvault.example", "employment_verification")
    _issue_credential("verifier@trustvault.example", "verifier_license")

    upl = client.post(
        "/assets", headers=headers["holder"], files={"file": ("report.pdf", b"EMPLOYMENT REPORT", "application/pdf")}
    )
    assert upl.status_code == 200, upl.text
    asset_id = upl.json()["id"]

    pol = client.post(
        f"/assets/{asset_id}/policy",
        headers=headers["holder"],
        json={"requester_role": "verifier", "purpose": "employment", "min_trust": 50},
    )
    assert pol.status_code == 200, pol.text

    def request_access():
        r = client.post(
            "/access/request",
            headers=headers["verifier"],
            json={"asset_id": asset_id, "purpose": "employment"},
        )
        assert r.status_code == 200, r.text
        return r.json()

    def approve(req_id, duration=30):
        r = client.post(
            f"/access/{req_id}/approve",
            headers=headers["holder"],
            json={"decision": "approve", "duration_minutes": duration},
        )
        assert r.status_code == 200, r.text
        return r.json()

    return {
        "asset_id": asset_id,
        "headers": headers,
        "request_access": request_access,
        "approve": approve,
        "credential_id": holder_cred,
        "client": client,
        "org_id": org_id,
    }