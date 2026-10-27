from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CallLogBase(BaseModel):
    session_id: int
    tool_name: str = Field(max_length=64)
    params: Any | None = None
    result: Any | None = None
    latency_ms: int | None = None


class CallLogCreate(CallLogBase):
    pass


class CallLogRead(CallLogBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
