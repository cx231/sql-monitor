from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class InstanceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=1433, ge=1, le=65535)
    database_name: Optional[str] = Field(default=None, max_length=128)
    environment: str = Field(default="prod", min_length=1, max_length=32)
    collect_dsn: str = Field(min_length=1)
    kill_dsn: Optional[str] = None
    status: str = "disabled"
    collect_interval_seconds: int = Field(default=5, ge=1)
    retention_days: int = Field(default=7, ge=1)
    business_owner: Optional[str] = Field(default=None, max_length=128)
    dba_owner: Optional[str] = Field(default=None, max_length=128)
    sqlserver_version: Optional[str] = Field(default=None, max_length=128)


class InstanceUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    database_name: Optional[str] = Field(default=None, max_length=128)
    environment: str = Field(min_length=1, max_length=32)
    collect_dsn: str = Field(min_length=1)
    kill_dsn: Optional[str] = None
    status: str
    collect_interval_seconds: int = Field(ge=1)
    retention_days: int = Field(ge=1)
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
    collect_dsn: str
    kill_dsn: Optional[str] = None
    status: str
    collect_interval_seconds: int
    retention_days: int
    business_owner: Optional[str] = None
    dba_owner: Optional[str] = None
    sqlserver_version: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

