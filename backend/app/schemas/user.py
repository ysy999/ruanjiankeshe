from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    username: str = Field(max_length=64)
    style_preference: str | None = Field(default=None, max_length=64)


class UserCreate(UserBase):
    password_hash: str = Field(max_length=255)


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
