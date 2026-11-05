from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.visitor import resolve_visitor
from app.exceptions import ChatException
from app.models import Session as ChatSession
from app.services.orchestrator import handle_chat

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    session_id: int
    message: str = Field(min_length=1, max_length=20000)


@router.post("/chat")
def chat(
    payload: ChatRequest,
    response: Response,
    x_visitor_id: str | None = Header(default=None, alias="X-Visitor-Id"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    visitor_id = x_visitor_id or str(uuid4())
    response.headers["X-Visitor-Id"] = visitor_id
    user = resolve_visitor(db, visitor_id)
    session = db.scalar(
        select(ChatSession).where(ChatSession.id == payload.session_id, ChatSession.user_id == user.id)
    )
    if session is None:
        raise ChatException(404, "session not found")

    db.close()
    return StreamingResponse(
        handle_chat(str(session.id), payload.message.strip(), visitor_id),
        media_type="text/event-stream",
        headers={"X-Visitor-Id": visitor_id},
    )
