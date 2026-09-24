# TrustVault V2 — 3–5 Minute Demo Script

Tagline: **Verify once. Control access everywhere.**

The Ravi (holder) journey: login → education VC → encrypted upload + NFT →
context-aware policy → ALLOW → RESTRICTED without context → QR proof →
NFT transfer → simulated attack → STEP_UP → revocation → duress freeze →
anchored audit + offline sync.

## Prerequisite

Backend up with seeded users (local, all free):

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\reset_db.py --yes
$env:RATE_LIMIT_MAX = "500"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Enable the optional attack extras (only if the judges want them live):

```powershell
$env:ML_ANOMALY_ENABLED = "true"      # Isolation-Forest anomaly layer
$env:DURESS_ENABLED = "true"          # duress-freeze module
# restart uvicorn after setting either
```

## The script (read while the screen is on)

### 1. Login — passkeys, issued once (0:00–0:30)

Four seeded demo identities log in: **admin@**, **issuer@**, **holder@**,
**verifier@trustvault.example**. WebAuthn ceremony with dev fallback; the API
never sees a password.

> Say it: *"The institution verified Ravi once. Every later access is governed
> by policy + live trust, not by a stored credential."*

### 2. Issue an education VC (hash-only) (0:30–1:00)

The issuer emits an **education_certificate** credential for Ravi (IIT, Mumbai).
On-chain and in the DB you see **only the SHA-256 hash and status** — never the
document. Ravi's credential now feeds the trust engine.

### 3. Encrypted upload + ERC-721 custody (1:00–1:30)

Ravi uploads an encrypted document (`resume-proof.pdf`). The backend:

1. AES-256-GCM encrypts it → ciphertext to local `storage/`,
2. records the SHA-256 integrity hash + `AssetRegistry` anchor,
3. **mints an ERC-721 NFT** (`nft_token_id`) proving custody — with
   `CHAIN_ENABLED=true` the token id shows in the Assets panel, visible after
   upload arrows. Transfer is one click.

### 4. Context-aware policy (1:30–2:00)

Ravi scopes a policy: **verifier role, purpose `employment`, min trust 60,
location `HQ-Floor-3` (non-strict), business hours 09:00–18:00**.

Then:
- Request + approve a **30-minute** grant → download with location header
  `HQ-Floor-3` → **ALLOW**, content round-trips byte-for-byte.
- Download **without** the location header →
  **RESTRICTED** (`LOCATION_MISSING`) — 403, read-only, content never exposed,
  human explanation shown.

> Say it: *"Missing context never leaks data — it degrades to RESTRICTED.
> Non-strict means a *simulated* context breach just throttles; it never
> unlocks anything."*

### 5. QR proof, on demand (2:00–2:20)

Ravi generates a short-lived (5-min) QR token scoped `contract-signing`. The
verifier opens the **Verify** tab (or `/verify?token=...`), scans, and the
credential status + purpose render live. Verify is deliberately public —
proving is not a secret.

### 6. NFT custody transfer (2:20–2:45)

Ravi transfers the asset's NFT custody to the verifier identity (one click in
the Assets panel). The ownership rail now shows the full custody history; the
transfer is a first-class, anchored audit event.

### 7. Attack — watch trust collapse (2:45–4:00)

Run `scripts/attack_sim.py`. A forged JWT + IDOR attempt bounce (DENY), then a
velocity + auth-failure storm impersonating the verifier:

- Trust drops → clean download flips **ALLOW → STEP_UP**
  (`REQUEST_VELOCITY_HIGH`, identity penalty),
- credential revoked → **DENY** `CREDENTIAL_REVOKED` instantly,
- with `DURESS_ENABLED=true`: Ravi triggers duress (hide-in-plain-sight) and
  even *his own* sensitive access freezes `DENY` `DURESS_ACTIVE` until the PIN
  deactivates it.

> Say it: *"The blockchain proves what happened; the Trust Engine decides what
> happens next. The attack is visible, explainable, and reversible."*

### 8. Audit trail + offline sync + recovery (4:00–4:30)

The Dashboard **technical** view (admin/auditor) shows KPIs, pending grants,
and every high-value event with its **anchor + tx hash** on Sepolia. With
`RPC_URL` + `PRIVATE_KEY` configured, pending anchors promote at startup.
The Offline rail shows queued events reconciling (`/offline/sync`), and the
Recovery rail shows emitted holder-recovery requests + decisions.

> Say it: *"Every decision explainable, every high-value event anchored,
> offline decisions eventually reconciled. No raw data ever touches the chain."*

## Reset between runs

```powershell
.\.venv\Scripts\python.exe scripts\reset_db.py --yes   # then restart the API
```

## What the judges must see

| Beat | Where |
|------|-------|
| ALLOW → RESTRICTED (context) → STEP_UP → DENY | `scripts/demo.py` + `scripts/attack_sim.py` |
| ERC-721 NFT custody + transfer | Assets panel / `GET /assets/{id}/ownership` |
| QR proof flow | Verify tab / `POST /credentials/qr/{generate,verify}` |
| Duress freeze (optional) | `DURESS_ENABLED=true` then attack_sim stage H |
| Real testnet tx hash | Dashboard technical view or `GET /audit/{asset_id}` |
| Encrypted round-trip + offline sync | `scripts/demo.py` stages 5 & 10 |

## Going live on Sepolia (if network is up)

`cd contracts`; set `RPC_URL`/`PRIVATE_KEY` in `contracts/.env`;
`npx hardhat run scripts/deploy.ts --network sepolia`; paste the printed
addresses into `backend/.env`, set `CHAIN_ENABLED=true`. Uploads mint live NFTs
and pending anchors confirm on-chain.