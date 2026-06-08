from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

SqlSortBy = Literal[
    "duration_ms",
    "cpu_time_ms",
    "logical_reads",
    "reads",
    "writes",
    "wait_time_ms",
]
SortOrder = Literal["asc", "desc"]


class SqlListItem(BaseModel):
    session_id: int
    request_id: Optional[int] = None
    database_name: Optional[str] = None
    status: Optional[str] = None
    command: Optional[str] = None
    duration_ms: Optional[int] = None
    cpu_time_ms: Optional[int] = None
    logical_reads: Optional[int] = None
    reads: Optional[int] = None
    writes: Optional[int] = None
    wait_type: Optional[str] = None
    wait_time_ms: Optional[int] = None
    blocking_session_id: Optional[int] = None
    sql_hash: Optional[str] = None
    normalized_sql_hash: Optional[str] = None
    sql_preview: Optional[str] = None
    sql_text: Optional[str] = None


class SqlListOut(BaseModel):
    instance_id: uuid.UUID
    frame_id: uuid.UUID
    snapshot_time: datetime
    collect_delay_seconds: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int
    items: list[SqlListItem]
