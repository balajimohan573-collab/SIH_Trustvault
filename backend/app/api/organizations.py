import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models import Organization, User
from app.schemas import OrganizationApplyRequest, OrganizationDecideRequest, OrganizationOut
from app.services import audit_trail

router = APIRouter(prefix="/organizations", tags=["organizations"])
log = logging.getLogger("trustvault.organizations")


@router.post("", response_model=OrganizationOut)
def apply_organization(
    body: OrganizationApplyRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Issuers apply with proof of institutional identity. An admin verifies."""
    existing = (
        db.query(Organization)
        .filter(
            (Organization.official_domain == body.official_domain.lower())
            | (Organization.org_identifier == body.org_identifier)
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Organization already registered")

    org = Organization(
        name=body.name.strip(),
        official_domain=body.official_domain.lower(),
        org_identifier=body.org_identifier,
        evidence_uri=body.evidence_uri,
        created_by=current.id,
        verification_status="pending",
    )
    db.add(org)
    db.flush()
    current.organization_id = org.id
    if current.role == "holder":
        current.role = "issuer"  # pending issuer until verified
    audit_trail.record(
        db, current.id, "organization_applied", "organization", org.id,
        metadata={"name": org.name, "domain": org.official_domain},
    )
    db.commit()
    db.refresh(org)
    return _out(org)


@router.get("", response_model=list[OrganizationOut])
def list_organizations(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(Organization).order_by(Organization.created_at.desc()).all()
    return [_out(o) for o in rows]


@router.get("/me", response_model=OrganizationOut | None)
def my_organization(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current.organization_id:
        return None
    org = db.get(Organization, current.organization_id)
    return _out(org) if org else None


@router.post("/{org_id}/decide", response_model=OrganizationOut)
def decide_organization(
    org_id: str,
    body: OrganizationDecideRequest,
    current: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Admin verifies or rejects an issuing organization (real trust decision)."""
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    next_status = "verified" if body.approve else "rejected"
    org.verification_status = next_status
    if body.approve:
        org.verified_by = current.id
        org.verified_at = datetime.utcnow()
    audit_trail.record(
        db, current.id, "organization_decided", "organization", org.id,
        metadata={"status": next_status, "note": body.note},
    )
    db.commit()
    db.refresh(org)
    return _out(org)


def _out(o: Organization) -> OrganizationOut:
    return OrganizationOut(
        id=o.id,
        name=o.name,
        official_domain=o.official_domain,
        org_identifier=o.org_identifier,
        verification_status=o.verification_status,
        verified_at=o.verified_at,
        created_at=o.created_at,
    )