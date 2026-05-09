from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

KillResult = Literal["success", "failed", "rejected"]


class KillRequest(BaseModel):
    instance_id: uuid.UUID
    session_id: int = Field(ge=1)
    reason: str = Field(min_length=1)


class KillResponse(BaseModel):
    audit_id: uuid.UUID
    instance_id: uuid.UUID
    session_id: int
    result: KillResult
    error_message: Optional[str] = None


class KillAuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    operator_user_id: Optional[uuid.UUID] = None
    operator_name: str
    instance_id: uuid.UUID
    session_id: int
    reason: str
    before_snapshot: dict[str, Any]
    result: KillResult
    error_message: Optional[str] = None
    created_at: datetime
