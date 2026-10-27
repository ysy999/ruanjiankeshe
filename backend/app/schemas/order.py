from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OrderBase(BaseModel):
    order_id: str = Field(max_length=32)
    user_id: int
    status: str = Field(max_length=32)
    logistics_company: str | None = Field(default=None, max_length=64)
    tracking_no: str | None = Field(default=None, max_length=64)
    items: Any | None = None


class OrderCreate(OrderBase):
    pass


class OrderRead(OrderBase):
    model_config = ConfigDict(from_attributes=True)
