from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DashboardMetrics(BaseModel):
    session_count: int
    active_request_count: int
    blocked_session_count: int
    root_blocker_count: int
    max_blocking_duration_ms: int
    waiting_request_count: int
    deadlocks_last_hour: int = 0


class TopWait(BaseModel):
    wait_type: str
    wait_category: str
    waiting_tasks_count: int
    total_wait_time_ms: int
    max_wait_time_ms: int


class TopSql(BaseModel):
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


class ResourceTrendPoint(BaseModel):
    snapshot_time: datetime
    cpu_load_percent: Optional[float] = None
    memory_usage_percent: Optional[float] = None
    network_send_rate_bytes_per_sec: Optional[float] = None
    network_receive_rate_bytes_per_sec: Optional[float] = None


class DashboardOut(BaseModel):
    instance_id: uuid.UUID
    frame_id: uuid.UUID
    snapshot_time: datetime
    collect_delay_seconds: int
    metrics_window_minutes: int = 5
    metrics: DashboardMetrics
    resource_trends: list[ResourceTrendPoint] = []
    top_waits: list[TopWait]
    top_cpu_sqls: list[TopSql]
    top_io_sqls: list[TopSql]
    top_tempdb_sessions: list[object] = []
    recent_events: list[object] = []
