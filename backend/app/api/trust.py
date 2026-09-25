from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas import TrustStateOut
from app.services.policy import build_context
from app.services.trust import evaluate_trust

router = APIRouter(prefix="/trust", tags=["trust"])


@router.get("/{user_id}", response_model=TrustStateOut)
def trust_state(
    user_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current explainable trust state for a user."""
    if (
        current.id != user_id
        and current.role != "admin"
    ):
        raise HTTPException(status_code=403, detail="Not authorized to view this trust state")

    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    context = build_context(db, target)
    state = evaluate_trust(context)
    return TrustStateOut(
        user_id=target.id,
        trust_score=state.trust_score,
        decision=state.decision,
        reasons=state.reasons,
        model_version=state.model_version,
        timestamp=datetime.now(timezone.utc),
        components=state.components,
        ml_signal=state.ml_signal,
    )


@router.post("/{user_id}/simulate")
def simulate_trust(
    user_id: str,
    mode: str = "normal",  # normal | step_up | blocked
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Simulate suspicious activity / risk state changes for demonstration."""
    raise HTTPException(
        status_code=410,
        detail="Simulation is not allowed in the real system. Read your live trust state at GET /trust/{user_id}.",
    )