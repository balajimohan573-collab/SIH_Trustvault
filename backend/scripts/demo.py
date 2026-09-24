"""TrustVault V2 demo runbook — the Ravi SIH happy-path story.

Requires backend running with seeded users:

    cd backend
    $env:RATE_LIMIT_MAX = "500"
    .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000

Then:  .\\.venv\\Scripts\\python.exe scripts\\demo.py

Prints a stage-by-stage narrative. Exit code 0 when every stage succeeds;
non-zero on the first failure (a demo shouldn't silently limp on).
"""
import sys
import time
import uuid

import httpx

BASE = "http://localhost:8000"


def step(client, method, path, token=None, ok_status=(200,), headers=None, **kw):
    merged = {"Authorization": f"Bearer {token}"} if token else {}
    if headers:
        merged.update(headers)
    r = client.request(method, path, headers=merged, **kw)
    if r.status_code not in ok_status:
        print(f"   !! stage failed: {method} {path} -> {r.status_code} {r.text[:200]}")
        sys.exit(1)
    return r


def main():
    with httpx.Client(timeout=30.0, base_url=BASE) as c:
        print("=" * 66)
        print("  TrustVault - Verify once. Control access everywhere.")
        print("  V2: 4-way decisions (ALLOW/STEP_UP/RESTRICTED/DENY),")
        print("      context-aware policies, ERC-721 asset custody, QR proof.")
        print("=" * 66)

        # 1. Login as the seeded roles (WebAuthn replaced by dev fallback so the
        #    demo runs without an authenticator).
        tk_issuer = step(c, "POST", "/auth/login/dev",
                         json={"email": "issuer@trustvault.example"}).json()["access_token"]
        holder = step(c, "POST", "/auth/login/dev",
                      json={"email": "holder@trustvault.example"}).json()
        verifier = step(c, "POST", "/auth/login/dev",
                        json={"email": "verifier@trustvault.example"}).json()
        tk_holder = holder["access_token"]
        tk_verifier = verifier["access_token"]
        step(c, "POST", "/auth/login/dev", json={"email": "admin@trustvault.example"})
        holder_user, verifier_user = holder["user"], verifier["user"]

        print("\n[1] Issuer issues Ravi's credential (hash-only, never raw docs)")
        cred = step(c, "POST", "/credentials/issue", token=tk_issuer, json={
            "holder_email": "holder@trustvault.example",
            "type": "education_certificate",
            "document": {"institution": "IIT, Mumbai", "degree": "B.Sc. CompSci", "name": "Ravi"},
        }).json()
        step(c, "POST", "/credentials/issue", token=tk_issuer, json={
            "holder_email": "verifier@trustvault.example",
            "type": "organisation",
            "document": {"institution": "Employer Co.", "role": "HR"},
        })
        print(f"    issued hash={cred['hash'][:16]}... status={cred['status']}")

        print("\n[2] Ravi uploads an encrypted document; an ERC-721 NFT is minted when chain is on")
        plaintext = b"Employment verification request " + uuid.uuid4().bytes
        asset = step(c, "POST", "/assets", token=tk_holder, ok_status=(200,),
                     files={"file": ("resume-proof.pdf", plaintext, "application/pdf")}).json()
        nft = asset.get("nft_token_id")
        print(f"    asset {asset['id'][:8]}... sha256={asset['file_hash'][:16]}... "
              f"NFT #{nft}" if nft else f"    asset {asset['id'][:8]}... sha256={asset['file_hash'][:16]}... "
              "NFT pending (chain disabled)")

        print("\n[3] Ravi defines a context-aware policy (verifier / employment / min trust 60 / HQ-Floor-3)")
        step(c, "POST", f"/assets/{asset['id']}/policy", token=tk_holder, ok_status=(200,),
             json={"requester_role": "verifier", "purpose": "employment", "min_trust": 60,
                   "location_scope": "HQ-Floor-3", "location_strict": False,
                   "time_start": "09:00", "time_end": "18:00"})
        print("    strict=False -> missing location degrades to RESTRICTED (read-only), never DENY")

        print("\n[4] Employer requests access; Ravi grants a time-bound token")
        req = step(c, "POST", "/access/request", token=tk_verifier, ok_status=(200,),
                   json={"asset_id": asset["id"], "purpose": "employment"}).json()
        grant = step(c, "POST", f"/access/{req['id']}/approve", token=tk_holder,
                     json={"decision": "approve", "duration_minutes": 30}).json()
        print(f"    grant purpose={grant['purpose']} expires={grant['expires_at'][:19]}")

        print("\n[5] Evaluate with a matching location context -> ALLOW (human-readable reasons)")
        ok = step(c, "GET", f"/assets/{asset['id']}/content", token=tk_verifier,
                  headers={"X-TrustVault-Location-Scope": "HQ-Floor-3"})
        assert ok.content == plaintext
        print(f"    served {len(ok.content)} bytes == original plaintext  ")

        print("\n[6] Evaluate with NO location context -> RESTRICTED (read-only, never exposes content)")
        denied = step(c, "GET", f"/assets/{asset['id']}/content", token=tk_verifier, ok_status=(403,))
        detail = denied.json()["detail"]
        print(f"    decision={detail['decision']} human='{detail['human']}' "
              f"scope={detail.get('scope')}")

        print("\n[7] Ravi generates a short-lived QR proof; employer verifies it publicly")
        qr = step(c, "POST", "/credentials/qr/generate", token=tk_holder, ok_status=(200,),
                  json={"credential_id": cred["id"], "purpose": "contract-signing"}).json()
        verified = step(c, "POST", "/credentials/qr/verify", json={"qr_token": qr["qr_token"]}).json()
        print(f"    valid={verified['valid']} status={verified['status']} "
              f"purpose={verified['purpose']} expires={verified['expires_at'][11:19]}")

        print("\n[8] Trust engine explains every decision")
        trust = step(c, "GET", f"/trust/{verifier_user['id']}", token=tk_verifier).json()
        print(f"    trust={trust['trust_score']} decision={trust['decision']} "
              f"model={trust['model_version']}")

        print("\n[9] Ravi transfers NFT custody to the employer (first-class audit event)")
        ownership = step(c, "POST", f"/assets/{asset['id']}/transfer", token=tk_holder, ok_status=(200,),
                         json={"to_user_id": verifier_user["id"], "reason": "handover after onboarding"}).json()
        print(f"    owner now={ownership['owner_id'][:8]}... history={len(ownership['history'])} event(s)")
        step(c, "POST", f"/assets/{asset['id']}/transfer", token=tk_verifier, ok_status=(200,),
             json={"to_user_id": holder_user["id"], "reason": "revert in demo"})

        print("\n[10] Every high-value event is anchored (and offline decisions sync on demand)")
        rows = step(c, "GET", f"/audit/{asset['id']}", token=tk_holder).json()
        shown = [r for r in rows if r.get("anchor")]
        for row in shown[-6:]:
            anchor = row["anchor"]
            print(f"    - {row['event_type']:<16} {anchor['chain']} "
                  f"[{anchor['status']}] {anchor['tx_hash'][:22]}")
        sync = step(c, "POST", "/offline/sync", token=tk_holder).json()
        print(f"    offline sync: {sync['synced']} event(s) reconciled")

        print("\n  Run scripts/attack_sim.py to see the attack story:")
        print("  trust collapse -> STEP_UP -> admin override -> revocation -> duress freeze.")
        print("DEMO COMPLETE")


if __name__ == "__main__":
    main()