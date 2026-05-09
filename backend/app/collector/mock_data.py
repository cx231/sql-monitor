from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.collector.blocking_graph import BlockingEdge, BlockingInput, build_blocking_edges
from app.collector.sql_text import normalized_sql_hash, preview_sql, sql_hash

DEFAULT_MOCK_INSTANCE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@dataclass(frozen=True)
class MockSession:
    session_id: int
    login_name: str
    host_name: str
    program_name: str
    database_name: str
    status: str
    open_transaction_count: int
    login_time: datetime
    last_request_start_time: Optional[datetime] = None
    last_request_end_time: Optional[datetime] = None
    cpu_time: int = 0
    reads: int = 0
    writes: int = 0
    logical_reads: int = 0
    current_sql_hash: Optional[str] = None


@dataclass(frozen=True)
class MockRequest:
    session_id: int
    request_id: int
    database_name: str
    status: str
    command: str
    start_time: datetime
    duration_ms: int
    cpu_time_ms: int
    total_elapsed_time_ms: int
    reads: int
    writes: int
    logical_reads: int
    row_count: int
    sql_text: str
    wait_type: Optional[str] = None
    wait_time_ms: Optional[int] = None
    blocking_session_id: Optional[int] = None
    percent_complete: Optional[float] = None
    plan_handle: Optional[bytes] = None
    statement_start_offset: int = 0
    statement_end_offset: int = -1
    resource_description: Optional[str] = None
    sql_hash: str = field(init=False)
    normalized_sql_hash: str = field(init=False)
    sql_preview: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sql_hash", sql_hash(self.sql_text))
        object.__setattr__(self, "normalized_sql_hash", normalized_sql_hash(self.sql_text))
        object.__setattr__(self, "sql_preview", preview_sql(self.sql_text, max_length=512))


@dataclass(frozen=True)
class MockWait:
    wait_type: str
    wait_category: str
    waiting_tasks_count: int
    total_wait_time_ms: int
    max_wait_time_ms: int


@dataclass(frozen=True)
class MockFrame:
    frame_id: uuid.UUID
    instance_id: uuid.UUID
    snapshot_time: datetime
    collect_duration_ms: int
    status: str
    sessions: tuple[MockSession, ...]
    requests: tuple[MockRequest, ...]
    waits: tuple[MockWait, ...]
    blocking_edges: tuple[BlockingEdge, ...]


def build_mock_frame(
    instance_id: Optional[uuid.UUID] = None,
    snapshot_time: Optional[datetime] = None,
) -> MockFrame:
    instance_id = instance_id or DEFAULT_MOCK_INSTANCE_ID
    snapshot_time = snapshot_time or datetime.now(timezone.utc)
    login_time = snapshot_time - timedelta(hours=2)

    high_io_sql = """
SELECT TOP (1000) *
FROM Sales.OrderLines
WHERE CustomerId = 4242
ORDER BY CreatedAt DESC
"""
    high_cpu_sql = """
SELECT p.ProductId, SUM(ol.Quantity * ol.UnitPrice) AS Revenue
FROM Sales.OrderLines AS ol
JOIN Production.Products AS p ON p.ProductId = ol.ProductId
GROUP BY p.ProductId
ORDER BY Revenue DESC
"""
    blocker_sql = """
UPDATE Inventory.Stock
SET Quantity = Quantity - 1
WHERE Sku = 'HOT-LOCK-001'
"""
    blocked_sql = """
UPDATE Inventory.Stock
SET ReservedQuantity = ReservedQuantity + 1
WHERE Sku = 'HOT-LOCK-001'
"""

    sessions = (
        MockSession(
            session_id=51,
            login_name="app_reader",
            host_name="web-01",
            program_name="SQLMon Mock Dashboard",
            database_name="Sales",
            status="sleeping",
            open_transaction_count=0,
            login_time=login_time,
            last_request_start_time=snapshot_time - timedelta(seconds=20),
            last_request_end_time=snapshot_time - timedelta(seconds=3),
            cpu_time=48_000,
            reads=8_800_000,
            writes=12,
            logical_reads=24_000_000,
            current_sql_hash=sql_hash(high_io_sql),
        ),
        MockSession(
            session_id=52,
            login_name="report_job",
            host_name="batch-01",
            program_name="Nightly Revenue Report",
            database_name="Sales",
            status="running",
            open_transaction_count=0,
            login_time=login_time - timedelta(hours=1),
            last_request_start_time=snapshot_time - timedelta(minutes=7),
            cpu_time=320_000,
            reads=4_200_000,
            writes=240,
            logical_reads=7_500_000,
            current_sql_hash=sql_hash(high_cpu_sql),
        ),
        MockSession(
            session_id=53,
            login_name="inventory_worker",
            host_name="worker-02",
            program_name="Inventory Sync",
            database_name="Inventory",
            status="sleeping",
            open_transaction_count=1,
            login_time=login_time - timedelta(minutes=25),
            last_request_start_time=snapshot_time - timedelta(minutes=3),
            cpu_time=15_000,
            reads=120_000,
            writes=8_900,
            logical_reads=320_000,
            current_sql_hash=sql_hash(blocker_sql),
        ),
        MockSession(
            session_id=54,
            login_name="checkout_api",
            host_name="api-03",
            program_name="Checkout API",
            database_name="Inventory",
            status="suspended",
            open_transaction_count=1,
            login_time=login_time - timedelta(minutes=10),
            last_request_start_time=snapshot_time - timedelta(seconds=45),
            cpu_time=4_000,
            reads=12_000,
            writes=300,
            logical_reads=44_000,
            current_sql_hash=sql_hash(blocked_sql),
        ),
    )

    requests = (
        MockRequest(
            session_id=52,
            request_id=0,
            database_name="Sales",
            status="running",
            command="SELECT",
            start_time=snapshot_time - timedelta(minutes=7),
            duration_ms=420_000,
            cpu_time_ms=360_000,
            total_elapsed_time_ms=420_000,
            reads=4_200_000,
            writes=240,
            logical_reads=7_500_000,
            row_count=1_000,
            sql_text=high_cpu_sql,
        ),
        MockRequest(
            session_id=54,
            request_id=0,
            database_name="Inventory",
            status="suspended",
            command="UPDATE",
            start_time=snapshot_time - timedelta(seconds=45),
            duration_ms=45_000,
            cpu_time_ms=2_200,
            total_elapsed_time_ms=45_000,
            reads=12_000,
            writes=300,
            logical_reads=44_000,
            row_count=0,
            sql_text=blocked_sql,
            wait_type="LCK_M_X",
            wait_time_ms=38_000,
            blocking_session_id=53,
            resource_description="KEY: 7:72057594040549376 (ce52f92a058c)",
        ),
    )

    waits = (
        MockWait(
            wait_type="LCK_M_X",
            wait_category="LOCK",
            waiting_tasks_count=1,
            total_wait_time_ms=38_000,
            max_wait_time_ms=38_000,
        ),
        MockWait(
            wait_type="PAGEIOLATCH_SH",
            wait_category="IO",
            waiting_tasks_count=3,
            total_wait_time_ms=12_400,
            max_wait_time_ms=5_200,
        ),
        MockWait(
            wait_type="SOS_SCHEDULER_YIELD",
            wait_category="CPU",
            waiting_tasks_count=5,
            total_wait_time_ms=8_600,
            max_wait_time_ms=2_100,
        ),
    )

    blocking_inputs = [
        BlockingInput(
            session_id=request.session_id,
            blocker_session_id=request.blocking_session_id,
            wait_type=request.wait_type,
            wait_duration_ms=request.wait_time_ms,
            resource_description=request.resource_description,
        )
        for request in requests
    ]

    return MockFrame(
        frame_id=uuid.uuid4(),
        instance_id=instance_id,
        snapshot_time=snapshot_time,
        collect_duration_ms=12,
        status="success",
        sessions=sessions,
        requests=requests,
        waits=waits,
        blocking_edges=tuple(build_blocking_edges(blocking_inputs)),
    )
