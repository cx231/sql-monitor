from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

InstanceStatus = Literal["online", "offline", "collect_error", "disabled"]


class InstanceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=1433, ge=1, le=65535)
    database_name: Optional[str] = Field(default=None, max_length=128)
    environment: str = Field(default="prod", min_length=1, max_length=32)
    collect_dsn: str = Field(min_length=1)
    kill_dsn: Optional[str] = None
    status: InstanceStatus = "disabled"
    collect_interval_seconds: int = Field(default=5, ge=1)
    retention_days: int = Field(default=7, ge=1)
    business_owner: Optional[str] = Field(default=None, max_length=128)
    dba_owner: Optional[str] = Field(default=None, max_length=128)
    sqlserver_version: Optional[str] = Field(default=None, max_length=128)


class InstanceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    host: Optional[str] = Field(default=None, min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    database_name: Optional[str] = Field(default=None, max_length=128)
    environment: Optional[str] = Field(default=None, min_length=1, max_length=32)
    collect_dsn: Optional[str] = Field(default=None, min_length=1)
    kill_dsn: Optional[str] = None
    status: Optional[InstanceStatus] = None
    collect_interval_seconds: Optional[int] = Field(default=None, ge=1)
    retention_days: Optional[int] = Field(default=None, ge=1)
    business_owner: Optional[str] = Field(default=None, max_length=128)
    dba_owner: Optional[str] = Field(default=None, max_length=128)
    sqlserver_version: Optional[str] = Field(default=None, max_length=128)


class InstanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    host: str
    port: int
    database_name: Optional[str] = None
    environment: str
    has_collect_dsn: bool
    has_kill_dsn: bool
    status: str
    collect_interval_seconds: int
    retention_days: int
    business_owner: Optional[str] = None
    dba_owner: Optional[str] = None
    sqlserver_version: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
