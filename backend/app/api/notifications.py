"""In-app notifications + a lightweight server-sent event stream.

`GET /notifications` — list, filter, mark read.
`GET /notifications/stream` — SSE: the client opens the stream, the server polls
the authoritative notifications table for rows newer than what this connection
has already seen and pushes them. Real, DB-driven, survives restarts.
"""
import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Notification, User
from app.schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])
log = logging.getLogger("trustvault.notifications")


def _out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        type=n.type,
        title=n.title,
        body=n.body,
        link=n.link,
        read=n.read_at is not None,
        created_at=n.created_at,
    )


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread: bool = False,
    limit: int = 50,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Notification).filter(Notification.user_id == current.id)
    if unread:
        q = q.filter(Notification.read_at.is_(None))
    rows = q.order_by(Notification.created_at.desc()).limit(min(limit, 200)).all()
    return [_out(n) for n in rows]


@router.get("/unread-count")
def unread_count(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = (
        db.query(Notification)
        .filter(Notification.user_id == current.id, Notification.read_at.is_(None))
        .count()
    )
    return {"unread": count}


@router.patch("/{notification_id}/read")
def mark_read(
    notification_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.get(Notification, notification_id)
    if not n or n.user_id != current.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    if n.read_at is None:
        n.read_at = datetime.utcnow()
        db.commit()
    return {"id": n.id, "read": True}


async def _stream_notifications(user_id: str):
    from app.db.session import SessionLocal

    seen: set[str] = set()
    with SessionLocal() as db:
        recent = (
            db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(20)
            .all()
        )
        for n in recent:
            seen.add(n.id)  # don't replay history on connect

    while True:
        with SessionLocal() as db:
            rows = (
                db.query(Notification)
                .filter(Notification.user_id == user_id)
                .order_by(Notification.created_at.desc())
                .limit(20)
                .all()
            )
        for n in reversed(rows):
            if n.id in seen:
                continue
            seen.add(n.id)
            yield f"data: {json.dumps(_out(n).model_dump())}\n\n"
        await asyncio.sleep(2)


@router.get("/stream")
def notifications_stream(
    current: User = Depends(get_current_user),
):
    return StreamingResponse(
        _stream_notifications(current.id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )