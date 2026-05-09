from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

SessionSortBy = Literal["session_id", "cpu_time", "reads", "writes", "logical_reads"]
SortOrder = Literal["asc", "desc"]


class SessionListItem(BaseModel):
    session_id: int
    login_name: Optional[str] = None
    host_name: Optional[str] = None
    program_name: Optional[str] = None
    database_name: Optional[str] = None
    status: Optional[str] = None
    open_transaction_count: int
    cpu_time: Optional[int] = None
    reads: Optional[int] = None
    writes: Optional[int] = None
    logical_reads: Optional[int] = None
    wait_type: Optional[str] = None
    wait_time_ms: Optional[int] = None
    blocking_session_id: Optional[int] = None
    current_sql_hash: Optional[str] = None
    current_sql_preview: Optional[str] = None


class SessionListOut(BaseModel):
    instance_id: uuid.UUID
    frame_id: uuid.UUID
    snapshot_time: datetime
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int
    items: list[SessionListItem]
