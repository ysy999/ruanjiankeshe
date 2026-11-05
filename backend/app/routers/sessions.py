from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.visitor import get_or_create_visitor
from app.exceptions import ChatException
from app.models import Message, Session as ChatSession, User

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    title: str = Field(default="新对话", max_length=255)


def success(data: Any, msg: str = "ok") -> dict[str, Any]:
    return {"code": 0, "msg": msg, "data": data}


def session_data(item: ChatSession) -> dict[str, Any]:
    return {
        "id": item.id,
        "user_id": item.user_id,
        "title": item.title,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.post("")
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_or_create_visitor),
) -> dict[str, Any]:
    item = ChatSession(user_id=user.id, title=payload.title)
    db.add(item)
    db.commit()
    db.refresh(item)
    return success(session_data(item), "session created")


@router.get("")
def list_sessions(
    db: Session = Depends(get_db), user: User = Depends(get_or_create_visitor)
) -> dict[str, Any]:
    items = db.scalars(
        select(ChatSession).where(ChatSession.user_id == user.id).order_by(ChatSession.updated_at.desc())
    ).all()
    return success([session_data(item) for item in items])


@router.get("/{session_id}/messages")
def list_messages(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_or_create_visitor),
) -> dict[str, Any]:
    item = db.scalar(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id))
    if item is None:
        raise ChatException(404, "session not found")
    messages = db.scalars(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at, Message.id)
    ).all()
    return success([
        {"id": row.id, "session_id": row.session_id, "role": row.role,
         "content": row.content, "citations": row.citations, "created_at": row.created_at}
        for row in messages
    ])


@router.delete("/{session_id}")
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_or_create_visitor),
) -> dict[str, Any]:
    item = db.scalar(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id))
    if item is None:
        raise ChatException(404, "session not found")
    db.delete(item)
    db.commit()
    return success({"id": session_id}, "session deleted")
