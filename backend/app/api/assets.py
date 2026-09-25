import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.crypto import sha256_hex
from app.db.session import get_db
from app.models import AccessGrant, AccessPolicy, Asset, AssetTransfer, TrustedDevice, User
from app.schemas import (
    AssetCreatePolicyRequest,
    AssetOwnershipOut,
    AssetPolicyOut,
    AssetTransferRequest,
    AssetUploadResponse,
)
from app.services import audit, chain, storage
from app.services.policy_explain import build_decision_out
from app.services.policy import (
    build_context,
    evaluate_access,
    find_active_grant,
    find_latest_grant,
    record_event,
)

router = APIRouter(prefix="/assets", tags=["assets"])
log = logging.getLogger("trustvault.assets")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB for the MVP


@router.post("", response_model=AssetUploadResponse)
async def upload_asset(
    file: UploadFile,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Encrypt + store + hash an asset, mint an NFT ownership token (best-effort).

    Pipeline: read bytes -> SHA-256 hash (plaintext integrity proof) ->
    AES-256-GCM encrypt -> write to local storage -> persist Asset row ->
    optional on-chain ERC-721 mint (AssetRegistry) when chain is enabled.
    """
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    try:
        _, relative_uri, file_hash = storage.save_encrypted(data)
    except storage.StorageError as exc:
        log.error("Storage failure: %s", exc)
        raise HTTPException(status_code=500, detail="Storage write failed") from exc

    # Best-effort NFT mint (no-op when chain disabled/unreachable).
    nft_token_id, chain_tx_hash = chain.register_asset_onchain(
        None, current.did or "", file_hash, None
    )

    asset = Asset(
        owner_id=current.id,
        name=file.filename or "untitled",
        encrypted_uri=relative_uri,
        file_hash=file_hash,
        cid=None,  # IPFS/S3 backend is future-scope; local storage is MVP.
        content_type=file.content_type or "application/octet-stream",
        nft_token_id=nft_token_id,
        chain_tx_hash=chain_tx_hash,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    record_event(db, current.id, "asset_created", asset_id=asset.id)
    audit.anchor(db, "asset_created", user_id=current.id, risk={"asset_id": asset.id})
    if nft_token_id:
        audit.anchor(
            db,
            "asset_minted",
            user_id=current.id,
            risk={"asset_id": asset.id, "nft_token_id": nft_token_id, "tx_hash": chain_tx_hash},
        )

    return AssetUploadResponse(
        id=asset.id,
        owner_id=asset.owner_id,
        name=asset.name,
        encrypted_uri=asset.encrypted_uri,
        file_hash=asset.file_hash,
        cid=asset.cid,
        content_type=asset.content_type,
        asset_class=asset.asset_class,
        nft_token_id=asset.nft_token_id,
        chain_tx_hash=asset.chain_tx_hash,
        created_at=asset.created_at,
    )


@router.get("", response_model=list[AssetUploadResponse])
def list_assets(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Assets owned by the current user, plus any asset the user holds a grant for."""
    owned = db.query(Asset).filter(Asset.owner_id == current.id).all()
    granted_ids = (
        db.query(AccessGrant.asset_id).filter(AccessGrant.requester_id == current.id).distinct()
    )
    granted = (
        db.query(Asset)
        .filter(Asset.id.in_(granted_ids), Asset.owner_id != current.id)
        .all()
    )
    rows = owned + granted
    return [
        AssetUploadResponse(
            id=a.id,
            owner_id=a.owner_id,
            name=a.name,
            encrypted_uri=a.encrypted_uri,
            file_hash=a.file_hash,
            cid=a.cid,
            content_type=a.content_type,
            asset_class=a.asset_class,
            nft_token_id=a.nft_token_id,
            chain_tx_hash=a.chain_tx_hash,
            created_at=a.created_at,
        )
        for a in rows
    ]


@router.get("/{asset_id}")
def get_asset(
    asset_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Asset metadata. Owner always allowed; others only via a valid grant.

    The full access-control pipeline (purpose, expiry, min trust, role) is
    applied to the content endpoint in Stage 4; metadata here is intentionally
    limited to owner/grantee.
    """
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    has_grant = (
        db.query(AccessGrant)
        .filter(AccessGrant.asset_id == asset_id, AccessGrant.requester_id == current.id)
        .first()
        is not None
    )
    if asset.owner_id != current.id and not has_grant:
        raise HTTPException(status_code=403, detail="Not authorized for this asset")

    return {
        "id": asset.id,
        "owner_id": asset.owner_id,
        "name": asset.name,
        "encrypted_uri": asset.encrypted_uri,
        "file_hash": asset.file_hash,
        "cid": asset.cid,
        "content_type": asset.content_type,
        "asset_class": asset.asset_class,
        "description": asset.description,
        "nft_token_id": asset.nft_token_id,
        "chain_tx_hash": asset.chain_tx_hash,
        "transferred_at": asset.transferred_at,
        "created_at": asset.created_at,
    }


@router.post("/{asset_id}/policy", response_model=AssetPolicyOut)
def create_policy(
    asset_id: str,
    body: AssetCreatePolicyRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Owner defines an ABAC policy: role + purpose + min trust + expiry.

    V2: policy may optionally declare location/time constraints (location is
    policy-based; requesters never enter GPS coordinates).
    """
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.owner_id != current.id and current.role != "admin":
        raise HTTPException(status_code=403, detail="Only the owner may create policies")

    policy = AccessPolicy(
        asset_id=asset.id,
        requester_role=body.requester_role,
        purpose=body.purpose,
        expires_at=body.expires_at,
        min_trust=body.min_trust,
        location_scope=body.location_scope,
        location_strict=body.location_strict,
        time_start=body.time_start,
        time_end=body.time_end,
        time_zone=body.time_zone,
        context_required=body.context_required,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return AssetPolicyOut(
        id=policy.id,
        asset_id=policy.asset_id,
        requester_role=policy.requester_role,
        purpose=policy.purpose,
        min_trust=policy.min_trust,
        expires_at=policy.expires_at,
        location_scope=policy.location_scope,
        location_strict=policy.location_strict,
        time_start=policy.time_start,
        time_end=policy.time_end,
        time_zone=policy.time_zone,
        context_required=policy.context_required,
    )


@router.post("/{asset_id}/transfer", response_model=AssetOwnershipOut)
def transfer_asset(
    asset_id: str,
    body: AssetTransferRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Transfer NFT-backed ownership of an asset to another user (owner only).

    Ownership transfer is a first-class, anchored audit event. The raw file is
    never moved — only the ownership token (and its grant surface).
    """
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.owner_id != current.id:
        raise HTTPException(status_code=403, detail="Only the current owner may transfer")
    to_user = db.get(User, body.to_user_id)
    if to_user is None:
        raise HTTPException(status_code=404, detail="Target user not found")
    if to_user.id == current.id:
        raise HTTPException(status_code=400, detail="Cannot transfer to self")

    old_owner = asset.owner_id
    asset.owner_id = to_user.id
    asset.transferred_at = datetime.utcnow()
    transfer = AssetTransfer(
        asset_id=asset.id,
        from_user_id=old_owner,
        to_user_id=to_user.id,
        reason=body.reason,
        chain_tx_hash=asset.chain_tx_hash,  # token stays the same; contract transfer is best-effort
    )
    db.add(transfer)
    db.commit()
    db.refresh(transfer)

    record_event(
        db,
        current.id,
        "asset_transferred",
        asset_id=asset.id,
        from_user_id=old_owner,
        to_user_id=to_user.id,
        reason=body.reason,
    )
    audit.anchor(
        db,
        "asset_transferred",
        user_id=current.id,
        risk={"asset_id": asset.id, "from_user_id": old_owner, "to_user_id": to_user.id},
    )
    return _ownership_out(db, asset)


@router.get("/{asset_id}/ownership", response_model=AssetOwnershipOut)
def get_ownership(
    asset_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ownership + full transfer history. Owner/admin only."""
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    has_grant = (
        db.query(AccessGrant)
        .filter(AccessGrant.asset_id == asset_id, AccessGrant.requester_id == current.id)
        .first()
        is not None
    )
    if asset.owner_id != current.id and current.role != "admin" and not has_grant:
        raise HTTPException(status_code=403, detail="Not authorized for this asset")
    return _ownership_out(db, asset)


def _ownership_out(db: Session, asset: Asset) -> AssetOwnershipOut:
    history = [
        {
            "id": t.id,
            "from_user_id": t.from_user_id,
            "to_user_id": t.to_user_id,
            "reason": t.reason,
            "created_at": t.created_at,
        }
        for t in db.query(AssetTransfer)
        .filter(AssetTransfer.asset_id == asset.id)
        .order_by(AssetTransfer.created_at.asc())
        .all()
    ]
    return AssetOwnershipOut(
        asset_id=asset.id,
        owner_id=asset.owner_id,
        nft_token_id=asset.nft_token_id,
        chain_tx_hash=asset.chain_tx_hash,
        transferred_at=asset.transferred_at,
        history=history,
    )


@router.get("/{asset_id}/content")
def download_asset_content(
    asset_id: str,
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the decrypted plaintext of an asset.

    This is the gate where the full RBAC+ABAC pipeline runs:
        authenticated -> credential valid -> role/permission -> purpose ->
        grant window -> trust threshold -> step-up -> audit.
    A real WebAuthn step-up re-assertion would happen between STEP_UP and a
    retry; the MVP returns the decision so the frontend can prompt re-auth.

    Admin override: `X-TrustVault-Admin-Override: 1` forces ALLOW only for the
    admin role, and always leaves an explicit privileged audit entry.
    """
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    admin_override = (
        current.role == "admin" and request.headers.get("X-TrustVault-Admin-Override") == "1"
    )
    grant = find_active_grant(db, asset, current)
    # Use the latest grant's purpose (even if expired) so the pipeline reports
    # GRANT_EXPIRED rather than masking it as a wrong/empty purpose.
    latest = find_latest_grant(db, asset, current)
    purpose = (grant or latest).purpose if (grant or latest) else None

    context = build_context(
        db,
        current,
        device_status=_current_device_status(db, current),
        extra={
            "asset_access": asset_id,
            "location_scope": request.headers.get("X-TrustVault-Location-Scope"),
        },
    )
    decision = evaluate_access(
        db, current, asset, purpose or "", context, check_grant=True, admin_override=admin_override
    )

    record_event(
        db,
        current.id,
        "access_" + decision.decision.lower(),
        decision,
        asset_id=asset.id,
        privileged=admin_override,
    )
    # High-value events get anchored (pending tx until Stage 6).
    if decision.decision in ("ALLOW", "DENY"):
        audit.anchor(
            db,
            "access_allowed" if decision.decision == "ALLOW" else "access_denied",
            user_id=current.id,
            risk={
                "asset_id": asset.id,
                "trust_score": decision.trust_score,
                "reasons": decision.reasons,
                "privileged": admin_override,
            },
        )

    if decision.decision != "ALLOW":
        human = build_decision_out(
            decision.decision,
            decision.reasons,
            decision.trust_score,
            decision.model_version,
            decision.scope,
        )
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Access denied by policy",
                "decision": decision.decision,
                "trust_score": decision.trust_score,
                "reasons": decision.reasons,
                "scope": decision.scope,
                "human": human.human,
                "next_action": human.next_action,
                "reasons_human": [r.model_dump() for r in human.reasons_human],
                "model_version": decision.model_version,
            },
        )

    try:
        plaintext = storage.load_decrypted(asset.encrypted_uri)
    except storage.StorageError as exc:
        log.error("Decryption failure for %s: %s", asset_id, exc)
        raise HTTPException(status_code=500, detail="Decryption failed") from exc

    return Response(
        content=plaintext,
        media_type=asset.content_type,
        headers={"Content-Disposition": f'attachment; filename="{asset.name}"'},
    )


def _current_device_status(db, user: User) -> str | None:
    device = (
        db.query(TrustedDevice)
        .filter(TrustedDevice.user_id == user.id)
        .order_by(TrustedDevice.last_seen.desc())
        .first()
    )
    # None = no device signal at all -> trust engine scores NO_DEVICE_TRACKING.
    return device.status if device else None