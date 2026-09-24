# TrustVault

**Verify once. Control access everywhere.**

A blockchain-anchored, privacy-preserving identity and access-control
platform (hackathon MVP). Institutions issue verifiable credentials once;
holders keep their documents encrypted and private; verifiers get scoped,
time-bound, purpose-limited access that a **Trust Engine** continuously
re-evaluates as the holder's security context evolves.

## Core principle

> The blockchain proves *what* was recorded. The Trust Engine decides
> *whether* a request satisfies the policy right now.

- On-chain: credential status, asset integrity hashes, access decisions,
  high-value audit events. **Never raw documents, PII profiles, or secrets.**
- Off-chain: document ciphertext (local AES-256-GCM storage in the MVP),
  the RBAC+ABAC policy engine, and the explainable Trust Engine.

## Architecture

```
 Issuer ──issues──▶ WebAuthn credential ──▶ Blockchain (Sepolia)
   │                                        IdentityRegistry (revocation)
   │   SHA-256 only                         AssetRegistry (integrity hashes)
   ▼                                        AccessControl  (decision anchors)
 Holder ──uploads──▶ Encrypted storage       AuditRegistry  (event anchors)
   │   AES-256-GCM (ciphertext never on chain)        ▲
   ▼                                            anchors (dropdown)
 Verifier ──request──▶  Policy pipeline (8 steps)
   │                    1-4 RBAC/ABAC (role, purpose, grant, expiry)
   │                    5-7 Trust Engine (identity/device/behaviour/
   │                     context/history) -> ALLOW | STEP_UP | RESTRICTED | DENY
   └──▶ Decision ──▶ Audit event ──▶ on-chain anchor
```

Monorepo layout:

| Path        | What                                    |
|-------------|-----------------------------------------|
| `backend/`  | FastAPI + SQLAlchemy API, policy + trust engine, audit anchoring (web3.py) |
| `frontend/` | React 19 + Vite + Tailwind v4 dashboard |
| `contracts/`| Hardhat + Solidity 0.8.25 (Cancun EVM) registry contracts |
| `docker-compose.yml` | Postgres 16 for when you want it |

## Quickstart (all free / open-source)

### 1. Backend

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\reset_db.py --yes     # seed 4 demo users
$env:RATE_LIMIT_MAX = "500"                               # room for the attack demo
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Demo users (WebAuthn dev-fallback login):
`admin@`, `issuer@`, `holder@`, `verifier@trustvault.example`.

Postgres (optional, if Docker is running): `docker compose up -d` and switch
`DATABASE_URL` in `backend/.env`.

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api -> :8000)
```

### 3. Contracts

```powershell
cd contracts
npm install
npx hardhat compile
npx hardhat test
npx hardhat run scripts/deploy.ts --network localhost   # smoke deploy
```

### 4. Backend tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v          # 23 V2 scenario tests
```

## Demo runbooks

| Script | Story |
|---|---|
| `DEMO_SCRIPT.md` | The 3–5 minute scripted demo (Ravi journey): login -> VC -> encrypted asset + NFT -> context policy -> ALLOW -> RESTRICTED -> QR proof -> transfer -> anchored audit |
| `backend/scripts/demo.py` | Ravi happy path: issue education VC -> upload encrypted doc (ERC-721 pending) -> context-aware policy -> time-bound grant -> ALLOW / RESTRICTED when context missing -> QR verify -> NFT transfer -> trust score -> audit anchors + offline sync |
| `backend/scripts/attack_sim.py` | Attack journey: forged JWT, IDOR, velocity/auth-failure storm collapses trust ALLOW->STEP_UP, RESTRICTED on context mismatch, admin override (audited), instant revocation, optional duress freeze |
| `backend/scripts/smoke_auth.py`, `smoke_assets.py` | Stage smoke checks (WebAuthn ceremony, encrypted round-trip) |

Reset between runs: `backend/scripts/reset_db.py --yes`, then restart the API.

## Trust Engine (V2, explainable)

Weighted, additive, fully explainable scores:

| Component (weight) | Signals |
|---|---|
| Identity (30%) | credential validity, recent auth failures |
| Device (20%) | known/active vs new/revoked |
| Behaviour (20%) | request velocity, access sequences |
| Context (15%) | unusual hour, geo penalty |
| History (15%) | recent anomaly decisions |

Four-way decision gate:

| Decision | Meaning |
|---|---|
| **ALLOW** | score ≥ 70 and every policy + context check passes |
| **STEP_UP** | score 40–69 (e.g. new device, velocity burst) — extra proof required |
| **RESTRICTED** | policy satisfiable but declared context is missing/mismatched (non-strict) — read-only, never exposes content |
| **DENY** | score < 40 **or any hard policy failure** (revoked credential/device, expired grant, wrong purpose, `DURESS_ACTIVE`) — always authoritative |

The AI/ML anomaly layer (`ML_ANOMALY_ENABLED=true`,
`ML_TRUST_CAP_DECISIONS_LEGACY=false` in V2) can only **downgrade** a decision
(never grant): ALLOW -> STEP_UP / RESTRICTED, STEP_UP -> DENY. Hard policy
failures always override the numeric score. Every endpoint returns a
human-readable explanation plus the exact reason codes used.

## API surface

| Area | Endpoints |
|---|---|
| Auth | `/auth/register/start|complete`, `/auth/login/start|complete`, `/auth/login/dev`, `/auth/me`, `/auth/logout`, `/auth/devices`, `GET /auth/users` |
| Credentials | `POST /credentials/issue`, `GET /credentials?holder=me`, `GET /credentials/{id}/verify`, `POST /credentials/{id}/revoke`, `POST /credentials/qr/generate`, `POST /credentials/qr/verify` (public) |
| Assets | `POST /assets`, `GET /assets`, `GET /assets/{id}/content`, `POST /assets/{id}/policy`, `POST /assets/{id}/transfer`, `GET /assets/{id}/ownership` |
| Access | `POST /access/request`, `GET /access`, `POST /access/{id}/approve|deny` |
| Trust & telemetry | `GET /trust/{user_id}`, `POST|GET /security/events` |
| Audit | `GET /audit/{asset_id}` (anchor status per event) |
| Dashboard | `GET /dashboard/summary?technical=` (role-scoped KPI + technical view) |
| Offline | `POST /offline/queue`, `POST /offline/sync`, `GET /offline/events` |
| Recovery | `POST /recovery/request`, `GET /recovery`, `POST /recovery/{id}/decide?status=` |
| Duress | `GET /duress/status`, `POST /duress/activate|deactivate` (feature-gated) |

Assets are ERC-721 NFTs: upload mints a token (when `CHAIN_ENABLED=true`),
transfers update on-chain custody, and `GET /assets/{id}/ownership` returns the
full custody history.

Admin override: `X-TrustVault-Admin-Override: 1` forces ALLOW **only** for
the admin role and always writes a privileged, anchored audit entry.

## Going live on Sepolia

1. Get a free-tier RPC (e.g. Alchemy/Infura) + a funded Sepolia test wallet.
2. `cd contracts`; put `RPC_URL`, `PRIVATE_KEY` in `contracts/.env`.
3. `npx hardhat run scripts/deploy.ts --network sepolia`.
4. Paste the four printed addresses into `backend/.env`
   (`*_REGISTRY_ADDRESS` + `RPC_URL` + `PRIVATE_KEY`).
5. Restart the backend: pending anchor rows promote to real transactions at
   startup and on every boot (`app/services/chain.py`).

## Explicitly excluded from the MVP (documented scope)

- No paid services: local encrypted storage, SQLite (Postgres optional), free
  testnet RPC, WebAuthn/passkeys, JWT — all free tiers.
- `JSON Web Token` sessions are in-memory (single instance); swap a store for
  HA.
- No delegation/escrow, no cap-recovery workflows, no email/SMS OTP channels.
- Frontend authenticates via the WebAuthn browser library; the API only
  accepts the completed ceremony payloads.

## See also

- `THREAT_MODEL.md` — assets, trust boundaries, attack/defense matrix, and
  the rationale behind every control.