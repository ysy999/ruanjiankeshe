from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageBase(BaseModel):
    session_id: int
    role: str = Field(max_length=32)
    content: str
    citations: Any | None = None


class MessageCreate(MessageBase):
    pass


class MessageRead(MessageBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
