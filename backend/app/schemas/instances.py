from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

InstanceStatus = Literal["online", "offline", "collect_error", "disabled"]


class InstanceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=1433, ge=1, le=65535)
    database_name: Optional[str] = Field(default=None, max_length=128)
    environment: str = Field(default="prod", min_length=1, max_length=32)
    collect_dsn: Optional[str] = Field(default=None, min_length=1)
    kill_dsn: Optional[str] = None
    username: Optional[str] = Field(default=None, min_length=1, max_length=128)
    password: Optional[str] = Field(default=None, min_length=1)
    status: InstanceStatus = "disabled"
    collect_interval_seconds: int = Field(default=5, ge=1)
    missing_index_collect_interval_seconds: int = Field(default=600, ge=60)
    index_fragmentation_collect_interval_seconds: int = Field(default=600, ge=60)
    index_operation_timeout_seconds: int = Field(default=1800, ge=30, le=7200)
    retention_days: int = Field(default=7, ge=1)
    business_owner: Optional[str] = Field(default=None, max_length=128)
    dba_owner: Optional[str] = Field(default=None, max_length=128)
    sqlserver_version: Optional[str] = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def require_collect_dsn_or_sql_auth(self) -> "InstanceCreate":
        if self.collect_dsn or (self.username and self.password):
            return self
        raise ValueError("必须提供采集 DSN 或 SQL 认证用户密码")


class InstanceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    host: Optional[str] = Field(default=None, min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    database_name: Optional[str] = Field(default=None, max_length=128)
    environment: Optional[str] = Field(default=None, min_length=1, max_length=32)
    collect_dsn: Optional[str] = Field(default=None, min_length=1)
    kill_dsn: Optional[str] = None
    username: Optional[str] = Field(default=None, min_length=1, max_length=128)
    password: Optional[str] = Field(default=None, min_length=1)
    status: Optional[InstanceStatus] = None
    collect_interval_seconds: Optional[int] = Field(default=None, ge=1)
    missing_index_collect_interval_seconds: Optional[int] = Field(default=None, ge=60)
    index_fragmentation_collect_interval_seconds: Optional[int] = Field(default=None, ge=60)
    index_operation_timeout_seconds: Optional[int] = Field(default=None, ge=30, le=7200)
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
    missing_index_collect_interval_seconds: int
    index_fragmentation_collect_interval_seconds: int
    index_operation_timeout_seconds: int
    retention_days: int
    business_owner: Optional[str] = None
    dba_owner: Optional[str] = None
    sqlserver_version: Optional[str] = None
    collect_status: Optional[str] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    last_duration_ms: Optional[int] = None
    consecutive_failures: int = 0
    collect_error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class InstanceConnectionTestRequest(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=1433, ge=1, le=65535)
    database_name: Optional[str] = Field(default="master", max_length=128)
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1)


class InstanceConnectionTestOut(BaseModel):
    success: bool
    sqlserver_version: Optional[str] = None
    database_name: Optional[str] = None
    databases: list[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    instance: Optional[InstanceOut] = None
