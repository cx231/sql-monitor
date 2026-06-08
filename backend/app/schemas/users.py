from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

UserRole = Literal["viewer", "developer", "dba", "admin"]
UserStatus = Literal["active", "disabled"]


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    display_name: Optional[str] = None
    role: UserRole
    status: UserStatus
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=256)
    display_name: Optional[str] = Field(default=None, max_length=128)
    role: UserRole


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=128)
    role: UserRole
    status: UserStatus


class UserPasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=256)
