from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.visitor import get_or_create_visitor
from app.exceptions import ChatException
from app.models import Feedback, Message, Session as ChatSession, User

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    session_id: int
    message_id: int
    score: int = Field(ge=-1, le=1)
    comment: str | None = None


def _result(data: Any, msg: str = "ok") -> dict[str, Any]:
    return {"code": 0, "msg": msg, "data": data}


@router.post("")
def create_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_or_create_visitor),
) -> dict[str, Any]:
    session = db.scalar(select(ChatSession).where(
        ChatSession.id == payload.session_id, ChatSession.user_id == user.id
    ))
    message = db.scalar(select(Message).where(
        Message.id == payload.message_id,
        Message.session_id == payload.session_id,
        Message.role == "assistant",
    ))
    if session is None or message is None:
        raise ChatException(404, "session or assistant message not found")
    feedback = Feedback(
        session_id=payload.session_id,
        message_id=payload.message_id,
        score=payload.score,
        comment=payload.comment,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return _result({"id": feedback.id, "reviewed": feedback.reviewed}, "feedback submitted")


@router.get("/pending")
def list_pending_feedback(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.execute(
        select(Feedback, Message.content)
        .join(Message, Message.id == Feedback.message_id)
        .where(Feedback.reviewed.is_(False))
        .order_by(Feedback.created_at.desc())
    ).all()
    data = [
        {
            "id": feedback.id,
            "session_id": feedback.session_id,
            "message_id": feedback.message_id,
            "score": feedback.score,
            "comment": feedback.comment,
            "created_at": feedback.created_at,
            "reviewed": feedback.reviewed,
            "message_content": content,
        }
        for feedback, content in rows
    ]
    return _result(data)
