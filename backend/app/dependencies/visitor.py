from uuid import uuid4

from fastapi import Depends, Header, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User


def resolve_visitor(db: Session, visitor_id: str) -> User:
    username = f"visitor-{visitor_id}"
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(username=username, password_hash="", style_preference="friendly")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_or_create_visitor(
    response: Response,
    x_visitor_id: str | None = Header(default=None, alias="X-Visitor-Id"),
    db: Session = Depends(get_db),
) -> User:
    visitor_id = x_visitor_id or str(uuid4())
    response.headers["X-Visitor-Id"] = visitor_id
    return resolve_visitor(db, visitor_id)
