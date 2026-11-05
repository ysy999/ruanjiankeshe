import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.visitor import get_or_create_visitor
from app.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    style: str = Field(default="friendly", pattern="^(formal|friendly|concise)$")
    length: str = Field(default="medium", pattern="^(short|medium|long)$")
    show_sources: bool = Field(
        default=True, validation_alias=AliasChoices("show_sources", "showSources")
    )
    nickname: str = Field(default="", max_length=80)


def success(data: Any, msg: str = "ok") -> dict[str, Any]:
    return {"code": 0, "msg": msg, "data": data}


def serialize_profile(user: User) -> dict[str, Any]:
    return {
        "style": user.style_preference or "friendly",
        "length": user.response_length or "medium",
        "show_sources": user.show_sources,
        "nickname": user.nickname or "",
    }


@router.get("")
def read_profile(user: User = Depends(get_or_create_visitor)) -> dict[str, Any]:
    return success(serialize_profile(user))


@router.put("")
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_or_create_visitor),
) -> dict[str, Any]:
    user.style_preference = payload.style
    user.response_length = payload.length
    user.show_sources = payload.show_sources
    user.nickname = payload.nickname
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("用户偏好已更新 visitor_id=%s", user.username.removeprefix("visitor-"))
    return success(serialize_profile(user), "用户偏好已更新")
