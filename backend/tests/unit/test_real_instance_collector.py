from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.collector.real_instance_collector import collect_instance_snapshot
from app.db.models import Instance, InstanceCollectStatus
from app.services.instance_service import encrypt_connection_string


class FakeSqlServerClient:
    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string
        self.calls: list[tuple[str, int | None]] = []

    def query(self, sql: str, timeout_seconds: int | None = None):
        self.calls.append((sql, timeout_seconds))
        if "dm_exec_sessions" in sql:
            return [
                {
                    "session_id": 51,
                    "login_name": "app_reader",
                    "host_name": "web-01",
                    "program_name": "订单服务",
                    "database_name": "master",
                    "session_status": "running",
                    "open_transaction_count": 1,
                    "login_time": datetime(2026, 5, 11, 9, 0, tzinfo=timezone.utc),
                    "last_request_start_time": datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc),
                    "last_request_end_time": None,
                    "session_cpu_time": 100,
                    "session_reads": 20,
                    "session_writes": 3,
                    "session_logical_reads": 400,
                    "request_id": 0,
                    "request_status": "suspended",
                    "command": "SELECT",
                    "start_time": datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc),
                    "request_cpu_time_ms": 50,
                    "total_elapsed_time_ms": 2_000,
                    "request_reads": 10,
                    "request_writes": 1,
                    "request_logical_reads": 200,
                    "row_count": 5,
                    "wait_type": "LCK_M_X",
                    "wait_time_ms": 1_200,
                    "blocking_session_id": 52,
                    "percent_complete": 0,
                    "sql_handle": b"sql-handle",
                    "plan_handle": b"plan-handle",
                    "statement_start_offset": 0,
                    "statement_end_offset": -1,
                    "sql_text": "SELECT * FROM dbo.Orders WHERE Id = 42",
                },
                {
                    "session_id": 52,
                    "login_name": "app_writer",
                    "host_name": "worker-01",
                    "program_name": "库存服务",
                    "database_name": "master",
                    "session_status": "running",
                    "open_transaction_count": 1,
                    "login_time": datetime(2026, 5, 11, 9, 5, tzinfo=timezone.utc),
                    "last_request_start_time": datetime(2026, 5, 11, 9, 55, tzinfo=timezone.utc),
                    "last_request_end_time": None,
                    "session_cpu_time": 300,
                    "session_reads": 40,
                    "session_writes": 9,
                    "session_logical_reads": 800,
                    "request_id": None,
                    "request_status": None,
                    "command": None,
                    "start_time": None,
                    "request_cpu_time_ms": None,
                    "total_elapsed_time_ms": None,
                    "request_reads": None,
                    "request_writes": None,
                    "request_logical_reads": None,
                    "row_count": None,
                    "wait_type": None,
                    "wait_time_ms": None,
                    "blocking_session_id": None,
                    "percent_complete": None,
                    "sql_handle": None,
                    "plan_handle": None,
                    "statement_start_offset": None,
                    "statement_end_offset": None,
                    "sql_text": None,
                },
            ]
        if "dm_os_waiting_tasks" in sql:
            return [
                {
                    "session_id": 51,
                    "exec_context_id": 0,
                    "wait_duration_ms": 1_200,
                    "wait_type": "LCK_M_X",
                    "blocking_session_id": 52,
                    "resource_description": "KEY: 7:123",
                }
            ]
        if "dm_os_ring_buffers" in sql:
            return [
                {
                    "cpu_load_percent": 23.5,
                    "memory_usage_percent": 64.25,
                    "network_bytes_total": 1_500_000,
                }
            ]
        raise AssertionError(f"unexpected SQL: {sql}")


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.committed = False
        self.rolled_back = False

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def test_collect_instance_snapshot_queries_sql_server_and_writes_snapshot_rows() -> None:
    instance_id = uuid.uuid4()
    instance = Instance(
        id=instance_id,
        name="主生产数据库",
        host="192.168.1.26",
        port=1433,
        database_name="master",
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("stored-dsn"),
        encrypted_kill_dsn=None,
        status="offline",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version=None,
    )
    collect_status = InstanceCollectStatus(
        instance_id=instance_id,
        consecutive_failures=3,
        status="failed",
        capabilities={},
    )
    fake_session = FakeSession()
    client = FakeSqlServerClient("stored-dsn")

    result = asyncio.run(
        collect_instance_snapshot(
            fake_session,
            instance,
            collect_status=collect_status,
            client_factory=lambda connection_string: client,
            now=lambda: datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        )
    )

    assert result.success is True
    assert result.frame_id is not None
    assert result.sessions_collected == 2
    assert result.requests_collected == 1
    assert result.waits_collected == 1
    assert result.blocking_edges_collected == 1
    assert instance.status == "online"
    assert collect_status.status == "success"
    assert collect_status.consecutive_failures == 0
    assert collect_status.last_success_at == datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    assert fake_session.committed is True

    added_types = [type(obj).__name__ for obj in fake_session.added]
    assert added_types.count("SnapshotFrame") == 1
    assert added_types.count("SessionSnapshot") == 2
    assert added_types.count("RequestSnapshot") == 1
    assert added_types.count("WaitSnapshot") == 1
    assert added_types.count("BlockingSnapshot") == 1
    assert added_types.count("SqlText") == 1

    frame = next(obj for obj in fake_session.added if type(obj).__name__ == "SnapshotFrame")
    request = next(obj for obj in fake_session.added if type(obj).__name__ == "RequestSnapshot")
    session_51 = next(
        obj
        for obj in fake_session.added
        if type(obj).__name__ == "SessionSnapshot" and obj.session_id == 51
    )
    assert request.sql_hash
    assert request.normalized_sql_hash
    assert request.duration_ms == 2_000
    assert request.plan_handle == b"plan-handle"
    assert session_51.current_sql_hash == request.sql_hash
    assert frame.cpu_load_percent == 23.5
    assert frame.memory_usage_percent == 64.25
    assert frame.network_bytes_total == 1_500_000


def test_collect_instance_snapshot_keeps_snapshot_when_resource_query_fails() -> None:
    instance_id = uuid.uuid4()
    instance = Instance(
        id=instance_id,
        name="主生产数据库",
        host="192.168.1.26",
        port=1433,
        database_name="master",
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("stored-dsn"),
        encrypted_kill_dsn=None,
        status="offline",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version=None,
    )
    collect_status = InstanceCollectStatus(
        instance_id=instance_id,
        consecutive_failures=0,
        status="unknown",
        capabilities={},
    )
    fake_session = FakeSession()

    class ResourceFailingClient(FakeSqlServerClient):
        def query(self, sql: str, timeout_seconds: int | None = None):
            if "dm_os_ring_buffers" in sql:
                raise RuntimeError("resource DMV denied")
            return super().query(sql, timeout_seconds)

    client = ResourceFailingClient("stored-dsn")

    result = asyncio.run(
        collect_instance_snapshot(
            fake_session,
            instance,
            collect_status=collect_status,
            client_factory=lambda connection_string: client,
            now=lambda: datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        )
    )

    assert result.success is True
    assert instance.status == "online"
    assert collect_status.status == "success"
    assert collect_status.capabilities["resources"] is False
    frame = next(obj for obj in fake_session.added if type(obj).__name__ == "SnapshotFrame")
    assert frame.cpu_load_percent is None
    assert frame.memory_usage_percent is None
    assert frame.network_bytes_total is None


def test_collect_instance_snapshot_marks_instance_collect_error_on_failure() -> None:
    instance_id = uuid.uuid4()
    instance = Instance(
        id=instance_id,
        name="主生产数据库",
        host="192.168.1.26",
        port=1433,
        database_name="master",
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("stored-dsn"),
        encrypted_kill_dsn=None,
        status="online",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version=None,
    )
    collect_status = InstanceCollectStatus(
        instance_id=instance_id,
        consecutive_failures=2,
        status="success",
        capabilities={},
    )
    fake_session = FakeSession()

    class FailingClient:
        def __init__(self, connection_string: str) -> None:
            self.connection_string = connection_string

        def query(self, sql: str, timeout_seconds: int | None = None):
            raise RuntimeError("login failed with sensitive details")

    result = asyncio.run(
        collect_instance_snapshot(
            fake_session,
            instance,
            collect_status=collect_status,
            client_factory=FailingClient,
            now=lambda: datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        )
    )

    assert result.success is False
    assert result.error_message == "采集失败"
    assert instance.status == "collect_error"
    assert collect_status.status == "failed"
    assert collect_status.consecutive_failures == 3
    assert collect_status.last_failure_at == datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    assert collect_status.error_message == "采集失败"
    assert fake_session.committed is True
