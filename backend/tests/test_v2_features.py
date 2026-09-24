"""V2 feature tests — QR verification, dashboard, offline sync, NFT transfer, duress."""
from app.core.config import get_settings


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------- QR
def test_qr_generate_and_verify_roundtrip(client, seed_users, dev_login):
    hh = _headers(dev_login("holder@trustvault.example"))
    hi = _headers(dev_login("issuer@trustvault.example"))

    cred = client.post(
        "/credentials/issue",
        headers=hi,
        json={
            "holder_email": "holder@trustvault.example",
            "type": "employment_verification",
            "document": {"degree": "BSc"},
        },
    )
    assert cred.status_code == 200, cred.text
    cid = cred.json()["id"]

    gen = client.post(
        "/credentials/qr/generate",
        headers=hh,
        json={"credential_id": cid, "purpose": "contract-signing"},
    )
    assert gen.status_code == 200, gen.text
    qr = gen.json()["qr_token"]

    # Public verify (no auth) — verifier simply scans the QR.
    v = client.post("/credentials/qr/verify", json={"qr_token": qr})
    assert v.status_code == 200, v.text
    body = v.json()
    assert body["valid"] is True
    assert body["id"] == cid
    assert body["purpose"] == "contract-signing"
    assert body["holder_did"] == "did:trustvault:holder"
    assert body["selective_disclosure_ready"] is True


def test_qr_tampered_token_is_rejected(client, seed_users, dev_login):
    hh = _headers(dev_login("holder@trustvault.example"))
    hi = _headers(dev_login("issuer@trustvault.example"))
    cid = client.post(
        "/credentials/issue",
        headers=hi,
        json={"holder_email": "holder@trustvault.example", "type": "id_card", "document": {"name": "A"}},
    ).json()["id"]
    qr = client.post(
        "/credentials/qr/generate", headers=hh, json={"credential_id": cid}
    ).json()["qr_token"]

    v = client.post("/credentials/qr/verify", json={"qr_token": qr + "x"})
    assert v.json()["valid"] is False
    assert v.json()["status"] == "invalid_token"


def test_qr_revoked_credential_reports_invalid(client, seed_users, dev_login):
    hh = _headers(dev_login("holder@trustvault.example"))
    hi = _headers(dev_login("issuer@trustvault.example"))
    cid = client.post(
        "/credentials/issue",
        headers=hi,
        json={"holder_email": "holder@trustvault.example", "type": "license", "document": {}},
    ).json()["id"]
    assert client.post(f"/credentials/{cid}/revoke", headers=hi, json={"reason": "fraud"}).status_code == 200

    qr = client.post(
        "/credentials/qr/generate", headers=hh, json={"credential_id": cid}
    ).json()["qr_token"]
    v = client.post("/credentials/qr/verify", json={"qr_token": qr}).json()
    assert v["valid"] is False
    assert v["status"] == "revoked"


# ---------------------------------------------------------------- Dashboard
def test_dashboard_admin_technical_view(client, seed_users, dev_login):
    b = client.get("/dashboard/summary?technical=true", headers=_headers(dev_login("admin@trustvault.example"))).json()
    assert b["user_role"] == "admin"
    assert b["identities"]["total_users"] == 4
    assert b["technical"]["flags"]["chain_enabled"] is False
    assert b["technical"]["counts"]["users"] == 4


def test_dashboard_holder_role_scoped(client, seed_users, dev_login):
    b = client.get("/dashboard/summary", headers=_headers(dev_login("holder@trustvault.example"))).json()
    assert b["user_role"] == "holder"
    assert b["identities"]["my_did"] == "did:trustvault:holder"
    assert b["technical"] is None  # holders do not get the technical view by default


# ---------------------------------------------------------------- Offline
def test_offline_queue_dedupes_and_syncs(client, seed_users, dev_login):
    hh = _headers(dev_login("holder@trustvault.example"))
    ev = {
        "event_type": "access_evaluation",
        "asset_id": "a-offline-001",
        "decision": "RESTRICTED",
        "reasons": ["LOCATION_MISSING"],
        "trust_score": 40,
        "payload": {"op": "read", "loc": "warehouse-offline"},
    }
    r1 = client.post("/offline/queue", headers=hh, json={"events": [ev]})
    assert r1.json()["received"] == 1 and r1.json()["synced"] == 1

    r2 = client.post("/offline/queue", headers=hh, json={"events": [ev]})
    assert r2.json()["received"] == 1 and r2.json()["deduped"] == 1

    s = client.post("/offline/sync", headers=hh)
    assert s.json()["synced"] == 1

    evs = client.get("/offline/events", headers=_headers(dev_login("admin@trustvault.example"))).json()
    assert any(e["sync_status"] == "synced" for e in evs)


# ---------------------------------------------------------------- NFT transfer
def test_asset_transfer_changes_owner(client, seed_users, dev_login):
    hh = _headers(dev_login("holder@trustvault.example"))
    hvi = _headers(dev_login("verifier@trustvault.example"))

    up = client.post("/assets", headers=hh, files={"file": ("doc.pdf", b"DATA", "application/pdf")})
    assert up.status_code == 200, up.text
    aid = up.json()["id"]
    verifier = seed_users["verifier"]

    tr = client.post(
        f"/assets/{aid}/transfer",
        headers=hh,
        json={"to_user_id": verifier.id, "reason": "handover"},
    )
    assert tr.status_code == 200, tr.text
    body = tr.json()
    assert body["owner_id"] == verifier.id
    assert len(body["history"]) == 1

    own = client.get(f"/assets/{aid}/ownership", headers=hvi)
    assert own.status_code == 200
    assert own.json()["owner_id"] == verifier.id

    # Old owner can no longer transfer or read.
    assert (
        client.post(
            f"/assets/{aid}/transfer",
            headers=hh,
            json={"to_user_id": seed_users["admin"].id},
        ).status_code
        == 403
    )


# ---------------------------------------------------------------- Duress
def test_duress_disabled_by_default(client, seed_users, dev_login):
    r = client.post("/duress/activate", headers=_headers(dev_login("holder@trustvault.example")))
    assert r.status_code == 400


def test_duress_activate_when_enabled(client, seed_users, dev_login, monkeypatch):
    monkeypatch.setattr(get_settings(), "duress_enabled", True)
    hh = _headers(dev_login("holder@trustvault.example"))
    r = client.post("/duress/activate", headers=hh)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["active"] is True
    st = client.get("/duress/status", headers=hh)
    assert st.json()["active"] is True
    d = client.post("/duress/deactivate", headers=hh)
    assert d.status_code == 200 and d.json()["active"] is False


def test_duress_freezes_sensitive_access(seeded_flow, monkeypatch):
    monkeypatch.setattr(get_settings(), "duress_enabled", True)
    f = seeded_flow
    req = f["request_access"]()
    f["approve"](req["id"])
    hv = f["headers"]["verifier"]

    r0 = f["client"].get(f"/assets/{f['asset_id']}/content", headers=hv)
    assert r0.status_code == 200

    assert f["client"].post("/duress/activate", headers=hv).status_code == 200
    r = f["client"].get(f"/assets/{f['asset_id']}/content", headers=hv)
    assert r.status_code == 403
    body = r.json()["detail"]
    assert body["decision"] == "DENY"
    assert "DURESS_ACTIVE" in body["reasons"]