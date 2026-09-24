"""On-chain anchoring for high-value audit events (web3.py).

Flows:
1. `anchor()` creates a `pending` AuditAnchor row (works offline).
2. `sync_pending(db)` — called at startup and on demand — submits pending
   anchors to the configured chain via the wallet in settings, then marks them
   `anchored` with the real tx hash.

When no RPC / private key / registry addresses are configured the system runs
fully off-chain: anchors stay `pending` and everything else works unchanged.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from web3 import Web3
from web3.exceptions import Web3Exception

from app.core.config import get_settings

settings = get_settings()
from app.models import AuditAnchor

log = logging.getLogger("trustvault.chain")

_EVENT_TYPE_TO_SIG = {
    "audit": "logEvent(bytes32,bytes32,address,string,uint96)",
    "identity": "revokeCredential(bytes32)",
}


def _get_rpc() -> Web3 | None:
    if not settings.chain_enabled or not settings.rpc_url:
        return None
    w3 = Web3(Web3.HTTPProvider(settings.rpc_url))
    return w3 if w3.is_connected() else None


def _wallet(w3: Web3, private_key: str):
    acct = w3.eth.account.from_key(private_key)
    return acct


# The ABI we need is the deployed AuditRegistry interface. We hard-code a
# minimal, stable slice; the full ABI is exported by hardhat as a JSON artifact.
_AUDIT_ABI = [
    {
        "type": "function",
        "name": "logEvent",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "eventId", "type": "bytes32"},
            {"name": "assetId", "type": "bytes32"},
            {"name": "actor", "type": "address"},
            {"name": "eventType", "type": "string"},
            {"name": "trustScore", "type": "uint96"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    }
]


def _submit_anchor(
    w3: Web3, private_key: str, address: str, row: AuditAnchor, nonce_offset: int = 0
) -> str:
    acct = _wallet(w3, private_key)
    contract = w3.eth.contract(address=Web3.to_checksum_address(address), abi=_AUDIT_ABI)

    event_id = bytes.fromhex(row.event_id.replace("-", "")).rjust(32, b"\x00")
    # asset scope: the anchor event itself has no asset scoping on-chain; we
    # forward a zero asset (event-level telemetry persists in the DB trail).
    asset_hash = bytes(32)

    call = contract.functions.logEvent(
        event_id,
        asset_hash,
        acct.address,
        "trustvault_audit",
        0,
    )
    nonce = w3.eth.get_transaction_count(acct.address) + nonce_offset
    tx = call.build_transaction(
        {
            "from": acct.address,
            "nonce": nonce,
            "gas": 200_000,
            "gasPrice": w3.eth.gas_price,
        }
    )
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return Web3.to_hex(tx_hash)


_ASSET_ABI = [
    # AssetRegistry (V2, ERC-721): mintAsset(address,bytes32,string,string) -> uint256
    {
        "type": "function",
        "name": "mintAsset",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "fileHash", "type": "bytes32"},
            {"name": "ownerDidRef", "type": "string"},
            {"name": "cid", "type": "string"},
        ],
        "outputs": [{"name": "tokenId", "type": "uint256"}],
    },
    {
        "type": "function",
        "name": "nextTokenId",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]


def register_asset_onchain(
    asset_id: str, owner_did: str, file_hash: str, cid: str | None = None
) -> tuple[str | None, str | None]:
    """Best-effort NFT mint on the AssetRegistry (ERC-721).

    Returns (token_id, tx_hash) or (None, None) when chain is not configured/
    reachable. Never blocks the upload path.
    """
    if not (
        settings.chain_enabled
        and settings.rpc_url
        and settings.private_key
        and settings.asset_registry_address
    ):
        return None, None
    w3 = _get_rpc()
    if w3 is None:
        return None, None
    try:
        acct = _wallet(w3, settings.private_key)
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(settings.asset_registry_address), abi=_ASSET_ABI
        )
        file_hash_bytes = w3.keccak(text=file_hash) if len(file_hash) != 66 else bytes.fromhex(file_hash[2:])
        pid = w3.keccak(text=f"trustvault:{asset_id}")
        owner_ref = owner_did or f"did:trustvault:ops:{pid.hex()}"
        call = contract.functions.mintAsset(acct.address, file_hash_bytes, owner_ref, cid or "")
        tx = call.build_transaction(
            {
                "from": acct.address,
                "nonce": w3.eth.get_transaction_count(acct.address),
                "gas": 200_000,
                "gasPrice": w3.eth.gas_price,
            }
        )
        signed = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        token_id = str(contract.functions.nextTokenId().call() - 1)
        log.info("Asset %s minted as NFT token %s -> %s", asset_id, token_id, Web3.to_hex(tx_hash))
        return token_id, Web3.to_hex(tx_hash)
    except Exception as exc:  # noqa: BLE001 - never block the upload path
        log.warning("Asset on-chain registration skipped for %s: %s", asset_id, exc)
        return None, None


def sync_pending(db: Session) -> int:
    """Submit all pending anchors to the configured chain. Returns #anchored."""
    pending = db.query(AuditAnchor).filter(AuditAnchor.tx_hash == "pending").all()
    if not pending:
        return 0

    cfg = settings
    rpc_url = cfg.rpc_url
    private_key = cfg.private_key
    audit_registry = cfg.audit_registry_address
    if not (cfg.chain_enabled and rpc_url and private_key and audit_registry):
        log.info("Chain not configured (rpc/private_key/registry) — %d anchor(s) stay pending", len(pending))
        return 0

    w3 = _get_rpc()
    if w3 is None:
        log.warning("RPC unreachable — %d anchor(s) stay pending", len(pending))
        return 0

    anchored = 0
    for offset, row in enumerate(pending):
        try:
            tx_hash = _submit_anchor(w3, private_key, audit_registry, row, nonce_offset=offset)
            row.tx_hash = tx_hash
            row.anchored_at = datetime.now(timezone.utc)
            anchored += 1
            log.info("Anchored event %s -> %s", row.event_id, tx_hash)
        except (Web3Exception, ValueError, Exception) as exc:  # noqa: BLE001
            log.warning("Anchor failed for event %s: %s", row.event_id, exc)
    db.commit()
    return anchored