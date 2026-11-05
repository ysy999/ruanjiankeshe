from sqlalchemy import select

from app.db import SessionLocal
from app.models import User


def get_profile(visitor_id: str) -> dict[str, str | bool]:
    """Return response preferences for a visitor, creating a default profile if needed."""
    username = f"visitor-{visitor_id}"
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(username=username, password_hash="", style_preference="friendly")
            db.add(user)
            db.commit()
            db.refresh(user)
        return {
            "style": user.style_preference or "friendly",
            "length": user.response_length or "medium",
            "show_sources": user.show_sources,
            "nickname": user.nickname or "",
        }
