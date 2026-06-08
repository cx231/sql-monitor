from __future__ import annotations

import asyncio
import threading
import time
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.collector import real_instance_collector
from app.collector.real_instance_collector import collect_instance_snapshot, list_collectable_instances
from app.db.models import (
    IndexCollectionStatus,
    IndexFragmentationSnapshot,
    Instance,
    InstanceCollectStatus,
    MissingIndexSnapshot,
)
from app.services.instance_service import encrypt_connection_string


class FakeSqlServerClient:
    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string
        self.calls: list[tuple[str, int | None]] = []

    def query(self, sql: str, parameters=None, timeout_seconds: int | None = None):
        self.calls.append((sql, timeout_seconds))
        normalized = sql.lower()
        if "from sys.databases" in normalized:
            return [
                {"database_name": "Orders"},
                {"database_name": "Inventory"},
            ]
        if "dm_db_missing_index_details" in normalized:
            return [
                {
                    "database_name": "Orders",
                    "schema_name": "sales",
                    "table_name": "OrderItems",
                    "equality_columns": "[CustomerId]",
                    "inequality_columns": "",
                    "included_columns": "[Amount]",
                    "user_seeks": 12,
                    "user_scans": 1,
                    "avg_total_user_cost": 25.5,
                    "avg_user_impact": 70.0,
                }
            ]
        if "dm_db_index_physical_stats" in normalized:
            return [
                {
                    "database_name": "Orders",
                    "schema_name": "sales",
                    "table_name": "OrderItems",
                    "index_name": "IX_OrderItems_Date",
                    "index_type": "NONCLUSTERED INDEX",
                    "partition_number": 1,
                    "avg_fragmentation_in_percent": 35.5,
                    "page_count": 5000,
                },
                {
                    "database_name": "Orders",
                    "schema_name": "sales",
                    "table_name": "Tiny",
                    "index_name": "IX_Tiny_Name",
                    "index_type": "NONCLUSTERED INDEX",
                    "partition_number": 1,
                    "avg_fragmentation_in_percent": 99.0,
                    "page_count": 100,
                },
            ]
        if "serverproperty" in normalized:
            return [{"engine_edition": 3, "edition": "Standard Edition", "product_major_version": 15}]
        if "sys.indexes" in normalized:
            return []
        if "dm_exec_sessions" in normalized:
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
        if "dm_os_waiting_tasks" in normalized:
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
        if "dm_os_ring_buffers" in normalized:
            return [
                {
                    "cpu_load_percent": 23.5,
                    "memory_usage_percent": 64.25,
                    "network_bytes_sent_total": 600_000,
                    "network_bytes_received_total": 900_000,
                }
            ]
        raise AssertionError(f"unexpected SQL: {sql}")


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.deleted = []
        self.committed = False
        self.commit_count = 0
        self.rolled_back = False
        self.rollback_count = 0

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rolled_back = True
        self.rollback_count += 1


class FakeExecutableSession(FakeSession):
    def __init__(self, rows=None) -> None:
        super().__init__()
        self.rows = rows or []

    async def execute(self, statement):
        return FakeExecuteResult(self.rows)


class FakeScalarResult:
    def __init__(self, rows) -> None:
        self.rows = rows

    def all(self):
        return self.rows


class FakeExecuteResult:
    def __init__(self, rows) -> None:
        self.rows = rows

    def scalars(self):
        return FakeScalarResult(self.rows)


class FakeCollectableSession:
    def __init__(self, instances, statuses) -> None:
        self.instances = instances
        self.statuses = statuses
        self.added = []

    async def execute(self, statement):
        return FakeExecuteResult(self.instances)

    async def get(self, model, key):
        return self.statuses.get(key)

    def add(self, obj) -> None:
        self.added.append(obj)


def test_list_collectable_instances_returns_every_enabled_instance() -> None:
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    first = Instance(
        id=first_id,
        name="生产一",
        host="192.168.1.26",
        port=1433,
        database_name="master",
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("first-dsn"),
        encrypted_kill_dsn=None,
        status="online",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version=None,
        missing_index_collect_interval_seconds=600,
        index_fragmentation_collect_interval_seconds=600,
    )
    second = Instance(
        id=second_id,
        name="生产二",
        host="192.168.1.27",
        port=1433,
        database_name="master",
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("second-dsn"),
        encrypted_kill_dsn=None,
        status="online",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version=None,
        missing_index_collect_interval_seconds=600,
        index_fragmentation_collect_interval_seconds=600,
    )
    first_status = InstanceCollectStatus(instance_id=first_id, status="success")
    second_status = InstanceCollectStatus(instance_id=second_id, status="success")
    fake_session = FakeCollectableSession(
        [first, second],
        {
            first_id: first_status,
            second_id: second_status,
        },
    )

    pairs = asyncio.run(list_collectable_instances(fake_session))

    assert pairs == [(first, first_status), (second, second_status)]


def test_collect_instance_snapshot_queries_sql_server_and_writes_snapshot_rows(capsys) -> None:
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
        missing_index_collect_interval_seconds=600,
        index_fragmentation_collect_interval_seconds=600,
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
    assert added_types.count("IndexCollectionStatus") == 4
    assert added_types.count("MissingIndexSnapshot") == 2
    assert added_types.count("IndexFragmentationSnapshot") == 2

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
    assert frame.network_bytes_sent_total == 600_000
    assert frame.network_bytes_received_total == 900_000
    fragmentation_snapshots = [
        obj for obj in fake_session.added if isinstance(obj, IndexFragmentationSnapshot)
    ]
    assert {item.index_name for item in fragmentation_snapshots} == {"IX_OrderItems_Date"}
    assert all(item.page_count >= 1000 for item in fragmentation_snapshots)
    assert all(item.avg_fragmentation_in_percent >= 5 for item in fragmentation_snapshots)
    output = capsys.readouterr().out
    assert (
        f"collector index snapshot instance_id={instance_id} database=Orders "
        "type=missing snapshots=1"
    ) in output
    assert (
        f"collector index snapshot instance_id={instance_id} database=Orders "
        "type=fragmentation scanned=2 snapshots=1"
    ) in output


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
        missing_index_collect_interval_seconds=600,
        index_fragmentation_collect_interval_seconds=600,
    )
    collect_status = InstanceCollectStatus(
        instance_id=instance_id,
        consecutive_failures=0,
        status="unknown",
        capabilities={},
    )
    fake_session = FakeSession()

    class ResourceFailingClient(FakeSqlServerClient):
        def query(self, sql: str, parameters=None, timeout_seconds: int | None = None):
            if "dm_os_ring_buffers" in sql:
                raise RuntimeError("resource DMV denied")
            return super().query(sql, parameters=parameters, timeout_seconds=timeout_seconds)

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
    assert frame.network_bytes_sent_total is None
    assert frame.network_bytes_received_total is None


def test_collect_instance_snapshot_commits_regular_snapshot_before_index_collection() -> None:
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
        missing_index_collect_interval_seconds=600,
        index_fragmentation_collect_interval_seconds=600,
    )
    collect_status = InstanceCollectStatus(
        instance_id=instance_id,
        consecutive_failures=0,
        status="unknown",
        capabilities={},
    )
    fake_session = FakeSession()

    class CommitObservingClient(FakeSqlServerClient):
        def query(self, sql: str, parameters=None, timeout_seconds: int | None = None):
            if "from sys.databases" in sql.lower():
                assert fake_session.commit_count == 1
            return super().query(sql, parameters=parameters, timeout_seconds=timeout_seconds)

    client = CommitObservingClient("stored-dsn")

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
    assert fake_session.commit_count >= 2


def test_collect_instance_snapshot_releases_status_read_transaction_before_index_queries() -> None:
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
        missing_index_collect_interval_seconds=600,
        index_fragmentation_collect_interval_seconds=600,
    )
    collect_status = InstanceCollectStatus(
        instance_id=instance_id,
        consecutive_failures=0,
        status="unknown",
        capabilities={},
    )
    fake_session = FakeExecutableSession()

    class RollbackObservingClient(FakeSqlServerClient):
        def query(self, sql: str, parameters=None, timeout_seconds: int | None = None):
            if "from sys.databases" in sql.lower():
                assert fake_session.rollback_count >= 1
            return super().query(sql, parameters=parameters, timeout_seconds=timeout_seconds)

    client = RollbackObservingClient("stored-dsn")

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
    assert fake_session.rollback_count >= 1
    assert any(isinstance(obj, MissingIndexSnapshot) for obj in fake_session.added)


def test_collect_instance_snapshot_uses_status_values_after_releasing_read_transaction() -> None:
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
        missing_index_collect_interval_seconds=600,
        index_fragmentation_collect_interval_seconds=600,
    )
    collect_status = InstanceCollectStatus(
        instance_id=instance_id,
        consecutive_failures=0,
        status="unknown",
        capabilities={},
    )

    class ExpiringStatus:
        def __init__(self) -> None:
            self.expired = False

        @property
        def index_type(self):
            if self.expired:
                raise RuntimeError("status object was accessed after transaction release")
            return "missing"

        @property
        def database_name(self):
            if self.expired:
                raise RuntimeError("status object was accessed after transaction release")
            return "Orders"

        @property
        def last_success_at(self):
            if self.expired:
                raise RuntimeError("status object was accessed after transaction release")
            return datetime(2026, 5, 11, 11, 55, tzinfo=timezone.utc)

    status = ExpiringStatus()

    class ExpiringStatusSession(FakeExecutableSession):
        async def rollback(self) -> None:
            await super().rollback()
            status.expired = True

    fake_session = ExpiringStatusSession([status])
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
    assert not any("dm_db_missing_index_details" in sql for sql, _ in client.calls)
    assert any("dm_db_index_physical_stats" in sql for sql, _ in client.calls)


def test_collect_instance_snapshot_collects_index_databases_concurrently() -> None:
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
        missing_index_collect_interval_seconds=600,
        index_fragmentation_collect_interval_seconds=600,
    )
    collect_status = InstanceCollectStatus(
        instance_id=instance_id,
        consecutive_failures=0,
        status="unknown",
        capabilities={},
    )
    fake_session = FakeSession()
    active_missing_queries = 0
    max_active_missing_queries = 0
    lock = threading.Lock()

    class ConcurrentClient(FakeSqlServerClient):
        def query(self, sql: str, parameters=None, timeout_seconds: int | None = None):
            nonlocal active_missing_queries, max_active_missing_queries
            normalized = sql.lower()
            if "from sys.databases" in normalized:
                return [{"database_name": "Orders"}, {"database_name": "Inventory"}]
            if "dm_db_missing_index_details" in normalized:
                with lock:
                    active_missing_queries += 1
                    max_active_missing_queries = max(max_active_missing_queries, active_missing_queries)
                time.sleep(0.02)
                try:
                    return super().query(sql, parameters=parameters, timeout_seconds=timeout_seconds)
                finally:
                    with lock:
                        active_missing_queries -= 1
            return super().query(sql, parameters=parameters, timeout_seconds=timeout_seconds)

    existing_statuses = [
        IndexCollectionStatus(
            instance_id=instance_id,
            database_name="Orders",
            index_type="fragmentation",
            status="success",
            last_success_at=datetime(2026, 5, 11, 11, 55, tzinfo=timezone.utc),
            item_count=1,
        )
    ]

    result = asyncio.run(
        collect_instance_snapshot(
            fake_session,
            instance,
            collect_status=collect_status,
            index_collection_statuses=existing_statuses,
            client_factory=lambda connection_string: ConcurrentClient(connection_string),
            now=lambda: datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        )
    )

    assert result.success is True
    assert max_active_missing_queries >= 2


def test_collect_instance_snapshot_records_worker_connection_failure_without_failing_instance() -> None:
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
        missing_index_collect_interval_seconds=600,
        index_fragmentation_collect_interval_seconds=600,
    )
    collect_status = InstanceCollectStatus(
        instance_id=instance_id,
        consecutive_failures=0,
        status="unknown",
        capabilities={},
    )
    fake_session = FakeSession()
    client_factory_calls = 0

    def client_factory(connection_string: str):
        nonlocal client_factory_calls
        client_factory_calls += 1
        if client_factory_calls >= 3:
            raise RuntimeError("worker connection failed")
        return FakeSqlServerClient(connection_string)

    result = asyncio.run(
        collect_instance_snapshot(
            fake_session,
            instance,
            collect_status=collect_status,
            client_factory=client_factory,
            now=lambda: datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        )
    )

    assert result.success is True
    assert collect_status.status == "success"
    failed_statuses = [
        obj for obj in fake_session.added
        if isinstance(obj, IndexCollectionStatus) and obj.status == "failed"
    ]
    assert failed_statuses
    assert {status.index_type for status in failed_statuses} == {"missing", "fragmentation"}
    assert all("worker connection failed" in str(status.error_message) for status in failed_statuses)


def test_collect_instance_snapshot_marks_slow_index_database_failed_without_blocking_others(
    monkeypatch,
) -> None:
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
        missing_index_collect_interval_seconds=600,
        index_fragmentation_collect_interval_seconds=600,
    )
    collect_status = InstanceCollectStatus(
        instance_id=instance_id,
        consecutive_failures=0,
        status="unknown",
        capabilities={},
    )
    fake_session = FakeSession()
    monkeypatch.setattr(
        real_instance_collector,
        "get_settings",
        lambda: SimpleNamespace(
            collect_query_timeout_seconds=3,
            index_collect_database_concurrency=2,
            index_collect_database_timeout_seconds=0.05,
        ),
    )

    class SlowFragmentationClient(FakeSqlServerClient):
        def query(self, sql: str, parameters=None, timeout_seconds: int | None = None):
            normalized = sql.lower()
            if "from sys.databases" in normalized:
                return [{"database_name": "Orders"}, {"database_name": "ATE"}]
            if (
                "dm_db_index_physical_stats" in normalized
                and parameters
                and parameters[0] == "ATE"
            ):
                time.sleep(0.2)
                return []
            return super().query(sql, parameters=parameters, timeout_seconds=timeout_seconds)

    started = time.monotonic()
    result = asyncio.run(
        collect_instance_snapshot(
            fake_session,
            instance,
            collect_status=collect_status,
            client_factory=SlowFragmentationClient,
            now=lambda: datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        )
    )
    elapsed = time.monotonic() - started

    assert result.success is True
    assert collect_status.status == "success"
    assert elapsed < 0.18
    assert any(
        isinstance(obj, IndexFragmentationSnapshot) and obj.database_name == "Orders"
        for obj in fake_session.added
    )
    failed_status = next(
        obj
        for obj in fake_session.added
        if isinstance(obj, IndexCollectionStatus)
        and obj.database_name == "ATE"
        and obj.index_type == "fragmentation"
    )
    assert failed_status.status == "failed"
    assert "超时" in str(failed_status.error_message)
    missing_status = next(
        obj
        for obj in fake_session.added
        if isinstance(obj, IndexCollectionStatus)
        and obj.database_name == "ATE"
        and obj.index_type == "missing"
    )
    assert missing_status.status == "success"


def test_index_database_timeout_does_not_count_time_waiting_in_executor_queue(
    monkeypatch,
) -> None:
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
        missing_index_collect_interval_seconds=600,
        index_fragmentation_collect_interval_seconds=600,
    )
    collect_status = InstanceCollectStatus(
        instance_id=instance_id,
        consecutive_failures=0,
        status="unknown",
        capabilities={},
    )
    fake_session = FakeSession()
    monkeypatch.setattr(
        real_instance_collector,
        "get_settings",
        lambda: SimpleNamespace(
            collect_query_timeout_seconds=3,
            index_collect_database_concurrency=1,
            index_collect_database_timeout_seconds=0.05,
        ),
    )

    class SlowButHealthyFragmentationClient(FakeSqlServerClient):
        def query(self, sql: str, parameters=None, timeout_seconds: int | None = None):
            normalized = sql.lower()
            if "from sys.databases" in normalized:
                return [
                    {"database_name": "Orders"},
                    {"database_name": "Inventory"},
                    {"database_name": "Billing"},
                ]
            if "dm_db_index_physical_stats" in normalized:
                time.sleep(0.02)
            return super().query(sql, parameters=parameters, timeout_seconds=timeout_seconds)

    existing_statuses = [
        IndexCollectionStatus(
            instance_id=instance_id,
            database_name="Orders",
            index_type="missing",
            status="success",
            last_success_at=datetime(2026, 5, 11, 11, 55, tzinfo=timezone.utc),
            item_count=1,
        )
    ]

    result = asyncio.run(
        collect_instance_snapshot(
            fake_session,
            instance,
            collect_status=collect_status,
            index_collection_statuses=existing_statuses,
            client_factory=SlowButHealthyFragmentationClient,
            now=lambda: datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        )
    )

    assert result.success is True
    fragmentation_statuses = [
        obj for obj in fake_session.added
        if isinstance(obj, IndexCollectionStatus) and obj.index_type == "fragmentation"
    ]
    assert {status.database_name for status in fragmentation_statuses} == {
        "Orders",
        "Inventory",
        "Billing",
    }
    assert all(status.status == "success" for status in fragmentation_statuses)


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
        missing_index_collect_interval_seconds=600,
        index_fragmentation_collect_interval_seconds=600,
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

        def query(self, sql: str, parameters=None, timeout_seconds: int | None = None):
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


def test_collect_instance_snapshot_skips_index_collection_when_not_due() -> None:
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
        missing_index_collect_interval_seconds=600,
        index_fragmentation_collect_interval_seconds=600,
    )
    collect_status = InstanceCollectStatus(
        instance_id=instance_id,
        consecutive_failures=0,
        status="unknown",
        capabilities={},
    )
    fake_session = FakeSession()
    client = FakeSqlServerClient("stored-dsn")
    last_success = datetime(2026, 5, 11, 11, 55, tzinfo=timezone.utc)
    existing_statuses = [
        IndexCollectionStatus(
            instance_id=instance_id,
            database_name="Orders",
            index_type="missing",
            status="success",
            last_success_at=last_success,
            item_count=1,
        ),
        IndexCollectionStatus(
            instance_id=instance_id,
            database_name="Orders",
            index_type="fragmentation",
            status="success",
            last_success_at=last_success,
            item_count=1,
        ),
    ]

    result = asyncio.run(
        collect_instance_snapshot(
            fake_session,
            instance,
            collect_status=collect_status,
            index_collection_statuses=existing_statuses,
            client_factory=lambda connection_string: client,
            now=lambda: datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        )
    )

    assert result.success is True
    assert not any("dm_db_missing_index_details" in sql for sql, _ in client.calls)
    assert not any("dm_db_index_physical_stats" in sql for sql, _ in client.calls)


def test_collect_instance_snapshot_ignores_wildcard_index_success_when_deciding_due() -> None:
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
        missing_index_collect_interval_seconds=86400,
        index_fragmentation_collect_interval_seconds=86400,
    )
    collect_status = InstanceCollectStatus(
        instance_id=instance_id,
        consecutive_failures=0,
        status="unknown",
        capabilities={},
    )
    fake_session = FakeSession()
    client = FakeSqlServerClient("stored-dsn")
    existing_statuses = [
        IndexCollectionStatus(
            instance_id=instance_id,
            database_name="*",
            index_type="missing",
            status="success",
            last_success_at=datetime(2026, 5, 11, 11, 55, tzinfo=timezone.utc),
            item_count=0,
        ),
        IndexCollectionStatus(
            instance_id=instance_id,
            database_name="*",
            index_type="fragmentation",
            status="success",
            last_success_at=datetime(2026, 5, 11, 11, 55, tzinfo=timezone.utc),
            item_count=0,
        ),
    ]

    result = asyncio.run(
        collect_instance_snapshot(
            fake_session,
            instance,
            collect_status=collect_status,
            index_collection_statuses=existing_statuses,
            client_factory=lambda connection_string: client,
            now=lambda: datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        )
    )

    assert result.success is True
    assert any("dm_db_missing_index_details" in sql for sql, _ in client.calls)
    assert any("dm_db_index_physical_stats" in sql for sql, _ in client.calls)
    assert any(isinstance(obj, MissingIndexSnapshot) for obj in fake_session.added)
    assert any(isinstance(obj, IndexFragmentationSnapshot) for obj in fake_session.added)


def test_collect_instance_snapshot_keeps_previous_index_snapshots_when_index_collection_fails() -> None:
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
        missing_index_collect_interval_seconds=600,
        index_fragmentation_collect_interval_seconds=600,
    )
    collect_status = InstanceCollectStatus(
        instance_id=instance_id,
        consecutive_failures=0,
        status="unknown",
        capabilities={},
    )
    fake_session = FakeSession()

    class IndexFailingClient(FakeSqlServerClient):
        def query(self, sql: str, parameters=None, timeout_seconds: int | None = None):
            if "from sys.databases" in sql.lower():
                raise RuntimeError("index collection failed")
            return super().query(sql, parameters=parameters, timeout_seconds=timeout_seconds)

    client = IndexFailingClient("stored-dsn")

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
    assert fake_session.committed is True
    assert not any(isinstance(obj, MissingIndexSnapshot) for obj in fake_session.added)
    assert not any(isinstance(obj, IndexFragmentationSnapshot) for obj in fake_session.added)
    failed_statuses = [
        obj for obj in fake_session.added
        if isinstance(obj, IndexCollectionStatus) and obj.status == "failed"
    ]
    assert {status.index_type for status in failed_statuses} == {"missing", "fragmentation"}
    assert all("index collection failed" in str(status.error_message) for status in failed_statuses)
