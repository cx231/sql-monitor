from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.db.models import (
    IndexCollectionStatus,
    IndexFragmentationSnapshot,
    Instance,
    MissingIndexSnapshot,
)
from app.services.index_service import (
    CreateIndexRequestData,
    FragmentationActionRequestData,
    IndexFragmentationItem,
    IndexSnapshotPage,
    IndexNameConflictError,
    MissingIndexCandidate,
    MissingIndexStore,
    build_create_index_sql,
    build_index_maintenance_sql,
    build_default_index_name,
    create_missing_index,
    execute_fragmentation_action,
    get_user_databases,
    get_missing_indexes,
    get_index_fragmentation,
    list_missing_indexes,
    list_index_fragmentation,
    list_user_databases,
    run_missing_index_ddl,
    run_fragmentation_ddl,
    supports_online_index_rebuild,
)
from app.services.instance_service import encrypt_connection_string


class FakeSqlServerClient:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.queries: list[tuple[str, tuple[object, ...]]] = []
        self.executed: list[str] = []
        self.database_rows = [
            {"database_name": "master"},
            {"database_name": "Orders"},
            {"database_name": "msdb"},
            {"database_name": "Inventory"},
        ]
        self.missing_rows: list[dict[str, object]] = []
        self.missing_total = 0
        self.fragmentation_rows: list[dict[str, object]] = []
        self.fragmentation_targets: list[dict[str, object]] = []
        self.version_rows: list[dict[str, object]] = []
        self.existing_names: set[str] = set()
        self.execution_timeouts: list[int | None] = []
        self.execute_exception: Exception | None = None

    def query(self, sql, parameters=None, timeout_seconds=None):
        self.queries.append((sql, tuple(parameters or ())))
        normalized = " ".join(sql.split()).lower()
        if "from sys.databases" in normalized:
            return self.database_rows
        if "serverproperty" in normalized:
            return self.version_rows
        if "from missing_index_candidates" in normalized and "count_big(*)" in normalized:
            return [{"total": self.missing_total or len(self.missing_rows)}]
        if "from missing_index_candidates" in normalized:
            start_row = int((parameters or [None, 1, len(self.missing_rows)])[1])
            end_row = int((parameters or [None, 1, len(self.missing_rows)])[2])
            return self.missing_rows[start_row - 1 : end_row]
        if "count_big(*)" in normalized:
            return [{"total": len(self.fragmentation_targets)}]
        if "dm_db_index_physical_stats" in normalized and "row_number() over" in normalized:
            start_row = int((parameters or [None, None, 1, len(self.fragmentation_targets)])[2])
            end_row = int((parameters or [None, None, 1, len(self.fragmentation_targets)])[3])
            targets = self.fragmentation_targets[start_row - 1 : end_row]
            rows: list[dict[str, object]] = []
            for target in targets:
                matches = [
                    row
                    for row in self.fragmentation_rows
                    if row.get("object_id") == target.get("object_id")
                    and row.get("index_id") == target.get("index_id")
                ]
                if matches:
                    rows.extend(matches)
                    continue
                rows.append(
                    {
                        **target,
                        "index_type": "",
                        "partition_number": 1,
                        "avg_fragmentation_in_percent": 0,
                        "page_count": 0,
                    }
                )
            return rows
        if "row_number() over" in normalized:
            start_row = int((parameters or [None, 1, len(self.fragmentation_targets)])[1])
            end_row = int((parameters or [None, 1, len(self.fragmentation_targets)])[2])
            return self.fragmentation_targets[start_row - 1 : end_row]
        if "dm_db_index_physical_stats" in normalized:
            object_id = (parameters or [None, None, None, None])[2]
            index_id = (parameters or [None, None, None, None])[3]
            if object_id is None or index_id is None:
                return self.fragmentation_rows
            return [
                row
                for row in self.fragmentation_rows
                if row.get("object_id") == object_id and row.get("index_id") == index_id
            ]
        if "sys.indexes" in normalized:
            return [{"name": name} for name in sorted(self.existing_names)]
        return self.missing_rows

    def execute(self, sql, timeout_seconds=None):
        self.execution_timeouts.append(timeout_seconds)
        if self.execute_exception is not None:
            raise self.execute_exception
        self.executed.append(sql)


class FakeSession:
    def __init__(self, instance: Instance | None):
        self.instance = instance
        self.missing_snapshots: list[MissingIndexSnapshot] = []
        self.fragmentation_snapshots: list[IndexFragmentationSnapshot] = []
        self.index_statuses: list[IndexCollectionStatus] = []
        self.added: list[object] = []
        self.committed = False
        self.refreshed: list[object] = []
        self.connection = "collect-dsn"

    async def get(self, model, instance_id):
        if model is MissingIndexStore:
            for audit in self.added:
                if isinstance(audit, MissingIndexStore) and audit.id == instance_id:
                    return audit
            return None
        if model is IndexCollectionStatus and isinstance(instance_id, dict):
            for status in self.index_statuses:
                if (
                    status.instance_id == instance_id["instance_id"]
                    and status.database_name == instance_id["database_name"]
                    and status.index_type == instance_id["index_type"]
                ):
                    return status
            return None
        if self.instance is None or self.instance.id != instance_id:
            return None
        return self.instance

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        self.refreshed.append(obj)

    async def execute(self, statement):
        text_value = str(statement).lower()
        if "missing_index_snapshots" in text_value:
            return FakeResult(_slice_statement_items(statement, self.missing_snapshots))
        if "index_fragmentation_snapshots" in text_value:
            return FakeResult(_slice_statement_items(statement, self.fragmentation_snapshots))
        if "index_collection_status" in text_value:
            return FakeResult(self.index_statuses)
        return FakeResult([])

    async def scalar(self, statement):
        text_value = str(statement).lower()
        if "missing_index_snapshots" in text_value:
            return len(self.missing_snapshots)
        if "index_fragmentation_snapshots" in text_value:
            return len(self.fragmentation_snapshots)
        return 0


class FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items

    def first(self):
        return (self._items[0],) if self._items else None


def _slice_statement_items(statement, items):
    offset_clause = getattr(statement, "_offset_clause", None)
    limit_clause = getattr(statement, "_limit_clause", None)
    offset = int(getattr(offset_clause, "value", 0) or 0)
    limit_value = getattr(limit_clause, "value", None)
    if limit_value is None:
        return items[offset:]
    return items[offset : offset + int(limit_value)]


def _instance(**overrides) -> Instance:
    values = {
        "id": uuid.uuid4(),
        "name": "核心库",
        "host": "10.0.8.12",
        "port": 1433,
        "database_name": "master",
        "environment": "prod",
        "encrypted_collect_dsn": encrypt_connection_string("collect-dsn"),
        "encrypted_kill_dsn": encrypt_connection_string("kill-dsn"),
        "status": "online",
        "collect_interval_seconds": 5,
        "missing_index_collect_interval_seconds": 600,
        "index_fragmentation_collect_interval_seconds": 600,
        "retention_days": 7,
        "business_owner": None,
        "dba_owner": None,
        "sqlserver_version": None,
    }
    values.update(overrides)
    return Instance(**values)


def _operator(role: str = "dba"):
    return SimpleNamespace(id=uuid.uuid4(), username="alice", role=role)


def test_list_user_databases_excludes_system_databases() -> None:
    client = FakeSqlServerClient("collect-dsn")

    result = list_user_databases(client)

    assert result == ["Orders", "Inventory"]


def test_get_user_databases_falls_back_to_instance_database_before_collector_status() -> None:
    instance = _instance(database_name="Orders")
    session = FakeSession(instance)

    result = asyncio.run(get_user_databases(session, instance.id))

    assert result == ["Orders"]


def test_get_user_databases_queries_instance_when_status_is_empty() -> None:
    instance = _instance(database_name="master")
    session = FakeSession(instance)
    client = FakeSqlServerClient("collect-dsn")

    result = asyncio.run(
        get_user_databases(
            session,
            instance.id,
            client_factory=lambda connection_string: client,
        )
    )

    assert result == ["Inventory", "Orders"]
    assert client.connection_string == "collect-dsn"
    assert any("from sys.databases" in sql.lower() for sql, _ in client.queries)


def test_get_user_databases_excludes_system_database_fallback() -> None:
    instance = _instance(database_name="master")
    session = FakeSession(instance)

    result = asyncio.run(get_user_databases(session, instance.id))

    assert result == []


def test_default_index_name_uses_key_columns_and_sequence_when_conflicting() -> None:
    client = FakeSqlServerClient("collect-dsn")
    client.existing_names = {
        "IX_OrderItems_CustomerId_CreatedAt",
        "IX_OrderItems_CustomerId_CreatedAt_001",
    }

    name = build_default_index_name(
        client,
        database_name="Orders",
        schema_name="dbo",
        table_name="OrderItems",
        key_columns=["CustomerId", "CreatedAt"],
    )

    assert name == "IX_OrderItems_CustomerId_CreatedAt_002"


def test_list_missing_indexes_maps_dmv_rows_and_generates_create_name() -> None:
    client = FakeSqlServerClient("collect-dsn")
    client.missing_rows = [
        {
            "database_name": "Orders",
            "schema_name": "sales",
            "table_name": "OrderItems",
            "equality_columns": "[CustomerId]",
            "inequality_columns": "[CreatedAt]",
            "included_columns": "[Amount], [Status]",
            "user_seeks": 42,
            "user_scans": 3,
            "avg_total_user_cost": 28.5,
            "avg_user_impact": 91.2,
        }
    ]

    result = list_missing_indexes(client, database_name="Orders")

    assert result == [
        MissingIndexCandidate(
            database_name="Orders",
            schema_name="sales",
            table_name="OrderItems",
            equality_columns=["CustomerId"],
            inequality_columns=["CreatedAt"],
            include_columns=["Amount", "Status"],
            user_seeks=42,
            user_scans=3,
            avg_total_user_cost=28.5,
            avg_user_impact=91.2,
            recommended_index_name="IX_OrderItems_CustomerId_CreatedAt",
            create_enabled=True,
            error_message=None,
        )
    ]


def test_list_missing_indexes_collects_all_pages_for_snapshot() -> None:
    client = FakeSqlServerClient("collect-dsn")
    client.missing_rows = [
        {
            "database_name": "Orders",
            "schema_name": "sales",
            "table_name": f"OrderItems{i}",
            "equality_columns": "[CustomerId]",
            "inequality_columns": "",
            "included_columns": "",
            "user_seeks": i,
            "user_scans": 0,
            "avg_total_user_cost": 10.0,
            "avg_user_impact": 80.0,
        }
        for i in range(1, 502)
    ]

    result = list_missing_indexes(client, database_name="Orders")

    assert len(result) == 501
    assert result[-1].table_name == "OrderItems501"
    missing_page_queries = [
        parameters
        for sql, parameters in client.queries
        if "FROM missing_index_candidates" in sql and "COUNT_BIG" not in sql
    ]
    assert missing_page_queries == [("Orders", 1, 500), ("Orders", 501, 1000)]


def test_list_missing_indexes_uses_lightweight_names_without_conflict_queries() -> None:
    client = FakeSqlServerClient("collect-dsn")
    client.existing_names = {"IX_OrderItems_CustomerId"}
    client.missing_rows = [
        {
            "database_name": "Orders",
            "schema_name": "sales",
            "table_name": "OrderItems",
            "equality_columns": "[CustomerId]",
            "inequality_columns": "",
            "included_columns": "",
            "user_seeks": 42,
            "user_scans": 0,
            "avg_total_user_cost": 10.0,
            "avg_user_impact": 80.0,
        }
    ]

    result = list_missing_indexes(client, database_name="Orders")

    assert result[0].recommended_index_name == "IX_OrderItems_CustomerId"
    assert not any("sys.indexes" in sql.lower() for sql, _ in client.queries)


def test_get_missing_indexes_pages_in_sql_server_and_names_only_current_page() -> None:
    instance = _instance()
    session = FakeSession(instance)
    collected_at = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    session.missing_snapshots = [
        MissingIndexSnapshot(
            id=uuid.uuid4(),
            instance_id=instance.id,
            database_name="Orders",
            schema_name="sales",
            table_name="OrderItems",
            equality_columns=["CustomerId"],
            inequality_columns=[],
            include_columns=[],
            user_seeks=15,
            user_scans=0,
            avg_total_user_cost=22.5,
            avg_user_impact=80.0,
            recommended_index_name="IX_OrderItems_CustomerId",
            collected_at=collected_at,
        ),
        MissingIndexSnapshot(
            id=uuid.uuid4(),
            instance_id=instance.id,
            database_name="Orders",
            schema_name="sales",
            table_name="Invoices",
            equality_columns=["OrderId"],
            inequality_columns=[],
            include_columns=[],
            user_seeks=12,
            user_scans=1,
            avg_total_user_cost=18.5,
            avg_user_impact=70.0,
            recommended_index_name="IX_Invoices_OrderId",
            collected_at=collected_at,
        ),
    ]
    session.index_statuses = [
        IndexCollectionStatus(
            instance_id=instance.id,
            database_name="Orders",
            index_type="missing",
            status="success",
            last_success_at=collected_at,
            item_count=2,
        )
    ]

    result = asyncio.run(
        get_missing_indexes(
            session,
            instance.id,
            "Orders",
            page=2,
            page_size=1,
            now=lambda: collected_at + timedelta(seconds=300),
        )
    )

    assert result is not None
    assert isinstance(result, IndexSnapshotPage)
    assert result.total == 2
    assert result.checked_at == collected_at
    assert result.collection_status == "success"
    assert result.collection_error is None
    assert result.stale is False
    assert [item.recommended_index_name for item in result.items] == ["IX_Invoices_OrderId"]


def test_get_missing_indexes_returns_only_requested_backend_page() -> None:
    instance = _instance()
    session = FakeSession(instance)
    collected_at = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    session.missing_snapshots = [
        MissingIndexSnapshot(
            id=uuid.uuid4(),
            instance_id=instance.id,
            database_name="Orders",
            schema_name="sales",
            table_name=f"OrderItems{i}",
            equality_columns=["CustomerId"],
            inequality_columns=[],
            include_columns=[],
            user_seeks=i,
            user_scans=0,
            avg_total_user_cost=float(i),
            avg_user_impact=80.0,
            recommended_index_name=f"IX_OrderItems{i}_CustomerId",
            collected_at=collected_at,
        )
        for i in range(1, 1001)
    ]

    result = asyncio.run(
        get_missing_indexes(
            session,
            instance.id,
            "Orders",
            page=2,
            page_size=20,
            now=lambda: collected_at,
        )
    )

    assert result is not None
    assert result.total == 1000
    assert len(result.items) == 20


def test_get_missing_indexes_uses_local_snapshots_without_sql_server_client() -> None:
    instance = _instance()
    session = FakeSession(instance)

    def forbidden_client_factory(connection_string: str):
        raise AssertionError("API reads local snapshots and must not connect to SQL Server")

    result = asyncio.run(
        get_missing_indexes(
            session,
            instance.id,
            "Orders",
            client_factory=forbidden_client_factory,
        )
    )

    assert result is not None
    assert result.items == []


def test_build_create_index_sql_quotes_identifiers_and_includes_columns() -> None:
    sql = build_create_index_sql(
        database_name="Orders",
        schema_name="sales",
        table_name="OrderItems",
        index_name="IX_OrderItems_CustomerId_CreatedAt",
        key_columns=["CustomerId", "CreatedAt"],
        include_columns=["Amount"],
    )

    assert sql == (
        "CREATE INDEX [IX_OrderItems_CustomerId_CreatedAt] "
        "ON [Orders].[sales].[OrderItems] ([CustomerId], [CreatedAt]) "
        "INCLUDE ([Amount])"
    )


def test_create_missing_index_falls_back_to_collect_dsn_when_kill_dsn_missing() -> None:
    instance = _instance(encrypted_kill_dsn=None)
    session = FakeSession(instance)
    client = FakeSqlServerClient("collect-dsn")

    response = asyncio.run(
        create_missing_index(
            session,
            CreateIndexRequestData(
                instance_id=instance.id,
                database_name="Orders",
                schema_name="sales",
                table_name="OrderItems",
                key_columns=["CustomerId"],
                include_columns=[],
                index_name="IX_OrderItems_CustomerId",
            ),
            operator=_operator(),
            client_factory=lambda connection_string: client,
        )
    )

    assert response.result == "running"
    assert client.connection_string == "collect-dsn"
    assert client.executed == []
    assert session.added[0].ddl_summary == (
        "CREATE INDEX [IX_OrderItems_CustomerId] "
        "ON [Orders].[sales].[OrderItems] ([CustomerId])"
    )


def test_create_missing_index_rejects_conflicting_user_index_name() -> None:
    instance = _instance()
    session = FakeSession(instance)
    client = FakeSqlServerClient("kill-dsn")
    client.existing_names = {"IX_OrderItems_CustomerId"}

    with pytest.raises(IndexNameConflictError):
        asyncio.run(
            create_missing_index(
                session,
                CreateIndexRequestData(
                    instance_id=instance.id,
                    database_name="Orders",
                    schema_name="sales",
                    table_name="OrderItems",
                    key_columns=["CustomerId"],
                    include_columns=[],
                    index_name="IX_OrderItems_CustomerId",
                ),
                operator=_operator(),
                client_factory=lambda connection_string: client,
            )
        )

    assert client.executed == []


def test_create_missing_index_executes_ddl_and_writes_audit() -> None:
    instance = _instance()
    session = FakeSession(instance)
    client = FakeSqlServerClient("kill-dsn")

    response = asyncio.run(
        create_missing_index(
            session,
            CreateIndexRequestData(
                instance_id=instance.id,
                database_name="Orders",
                schema_name="sales",
                table_name="OrderItems",
                key_columns=["CustomerId"],
                include_columns=["Amount"],
                index_name="IX_OrderItems_CustomerId",
            ),
            operator=_operator(),
            client_factory=lambda connection_string: client,
        )
    )

    assert response.result == "running"
    assert response.index_name == "IX_OrderItems_CustomerId"
    assert client.connection_string == "kill-dsn"
    assert client.executed == []
    assert isinstance(session.added[0], MissingIndexStore)
    assert session.added[0].result == "running"
    assert session.added[0].ddl_summary == (
        "CREATE INDEX [IX_OrderItems_CustomerId] "
        "ON [Orders].[sales].[OrderItems] ([CustomerId]) INCLUDE ([Amount])"
    )
    assert session.committed is True


def test_create_missing_index_returns_running_audit_without_executing_ddl() -> None:
    instance = _instance(index_operation_timeout_seconds=900)
    session = FakeSession(instance)
    client = FakeSqlServerClient("kill-dsn")

    response = asyncio.run(
        create_missing_index(
            session,
            CreateIndexRequestData(
                instance_id=instance.id,
                database_name="Orders",
                schema_name="sales",
                table_name="OrderItems",
                key_columns=["CustomerId"],
                include_columns=["Amount"],
                index_name="IX_OrderItems_CustomerId",
            ),
            operator=_operator(),
            client_factory=lambda connection_string: client,
        )
    )

    assert response.result == "running"
    assert response.error_message is None
    assert client.executed == []
    assert isinstance(session.added[0], MissingIndexStore)
    assert session.added[0].result == "running"
    assert session.added[0].ddl_summary == (
        "CREATE INDEX [IX_OrderItems_CustomerId] "
        "ON [Orders].[sales].[OrderItems] ([CustomerId]) INCLUDE ([Amount])"
    )


def test_run_missing_index_ddl_uses_instance_timeout_and_marks_success() -> None:
    instance = _instance(index_operation_timeout_seconds=900)
    session = FakeSession(instance)
    audit = MissingIndexStore(
        id=uuid.uuid4(),
        operator_user_id=uuid.uuid4(),
        operator_name="alice",
        instance_id=instance.id,
        database_name="Orders",
        schema_name="sales",
        table_name="OrderItems",
        index_name="IX_OrderItems_CustomerId",
        key_columns=["CustomerId"],
        include_columns=[],
        action="CREATE",
        partition_number=None,
        online_used=None,
        fragmentation_percent=None,
        page_count=None,
        ddl_summary="CREATE INDEX [IX_OrderItems_CustomerId] ON [Orders].[sales].[OrderItems] ([CustomerId])",
        result="running",
        error_message=None,
    )
    session.added.append(audit)
    client = FakeSqlServerClient("kill-dsn")

    asyncio.run(
        run_missing_index_ddl(
            session,
            audit.id,
            client_factory=lambda connection_string: client,
        )
    )

    assert client.connection_string == "kill-dsn"
    assert client.execution_timeouts == [900]
    assert audit.result == "success"
    assert audit.error_message is None
    assert session.committed is True


def test_run_missing_index_ddl_marks_timeout_failure() -> None:
    instance = _instance(index_operation_timeout_seconds=900)
    session = FakeSession(instance)
    audit = MissingIndexStore(
        id=uuid.uuid4(),
        operator_user_id=uuid.uuid4(),
        operator_name="alice",
        instance_id=instance.id,
        database_name="Orders",
        schema_name="sales",
        table_name="OrderItems",
        index_name="IX_OrderItems_CustomerId",
        key_columns=["CustomerId"],
        include_columns=[],
        action="CREATE",
        partition_number=None,
        online_used=None,
        fragmentation_percent=None,
        page_count=None,
        ddl_summary="CREATE INDEX [IX_OrderItems_CustomerId] ON [Orders].[sales].[OrderItems] ([CustomerId])",
        result="running",
        error_message=None,
    )
    session.added.append(audit)
    client = FakeSqlServerClient("kill-dsn")
    client.execute_exception = RuntimeError("HYT00", "Query timeout expired")

    asyncio.run(
        run_missing_index_ddl(
            session,
            audit.id,
            client_factory=lambda connection_string: client,
        )
    )

    assert client.execution_timeouts == [900]
    assert audit.result == "failed"
    assert audit.error_message == "INDEX_CREATE_TIMEOUT"


def test_create_missing_index_uses_configured_operation_timeout(monkeypatch) -> None:
    instance = _instance(index_operation_timeout_seconds=900)
    session = FakeSession(instance)
    audit = MissingIndexStore(
        id=uuid.uuid4(),
        operator_user_id=uuid.uuid4(),
        operator_name="alice",
        instance_id=instance.id,
        database_name="Orders",
        schema_name="sales",
        table_name="OrderItems",
        index_name="IX_OrderItems_CustomerId",
        key_columns=["CustomerId"],
        include_columns=[],
        action="CREATE",
        partition_number=None,
        online_used=None,
        fragmentation_percent=None,
        page_count=None,
        ddl_summary="CREATE INDEX [IX_OrderItems_CustomerId] ON [Orders].[sales].[OrderItems] ([CustomerId])",
        result="running",
        error_message=None,
    )
    session.added.append(audit)
    client = FakeSqlServerClient("kill-dsn")

    asyncio.run(run_missing_index_ddl(session, audit.id, client_factory=lambda _: client))

    assert audit.result == "success"
    assert client.execution_timeouts == [900]


def test_create_missing_index_reports_timeout_failure(monkeypatch) -> None:
    instance = _instance(index_operation_timeout_seconds=900)
    session = FakeSession(instance)
    audit = MissingIndexStore(
        id=uuid.uuid4(),
        operator_user_id=uuid.uuid4(),
        operator_name="alice",
        instance_id=instance.id,
        database_name="Orders",
        schema_name="sales",
        table_name="OrderItems",
        index_name="IX_OrderItems_CustomerId",
        key_columns=["CustomerId"],
        include_columns=[],
        action="CREATE",
        partition_number=None,
        online_used=None,
        fragmentation_percent=None,
        page_count=None,
        ddl_summary="CREATE INDEX [IX_OrderItems_CustomerId] ON [Orders].[sales].[OrderItems] ([CustomerId])",
        result="running",
        error_message=None,
    )
    session.added.append(audit)
    client = FakeSqlServerClient("kill-dsn")
    client.execute_exception = RuntimeError("HYT00", "Query timeout expired")

    asyncio.run(run_missing_index_ddl(session, audit.id, client_factory=lambda _: client))

    assert audit.result == "failed"
    assert audit.error_message == "INDEX_CREATE_TIMEOUT"
    assert client.execution_timeouts == [900]


def test_list_index_fragmentation_sorts_desc_and_recommends_actions() -> None:
    client = FakeSqlServerClient("collect-dsn")
    client.fragmentation_targets = [
        {
            "database_name": "Orders",
            "schema_name": "sales",
            "table_name": "Tiny",
            "object_id": 110,
            "index_id": 2,
            "index_name": "IX_Tiny_Name",
        },
        {
            "database_name": "Orders",
            "schema_name": "sales",
            "table_name": "OrderItems",
            "object_id": 120,
            "index_id": 2,
            "index_name": "IX_OrderItems_Date",
        },
        {
            "database_name": "Orders",
            "schema_name": "sales",
            "table_name": "Orders",
            "object_id": 130,
            "index_id": 2,
            "index_name": "IX_Orders_Customer",
        },
        {
            "database_name": "Orders",
            "schema_name": "sales",
            "table_name": "Customers",
            "object_id": 140,
            "index_id": 2,
            "index_name": "IX_Customers_Name",
        },
    ]
    client.fragmentation_rows = [
        {
            "object_id": 110,
            "index_id": 2,
            "database_name": "Orders",
            "schema_name": "sales",
            "table_name": "Tiny",
            "index_name": "IX_Tiny_Name",
            "index_type": "NONCLUSTERED INDEX",
            "partition_number": 1,
            "avg_fragmentation_in_percent": 99.0,
            "page_count": 100,
        },
        {
            "object_id": 120,
            "index_id": 2,
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
            "object_id": 130,
            "index_id": 2,
            "database_name": "Orders",
            "schema_name": "sales",
            "table_name": "Orders",
            "index_name": "IX_Orders_Customer",
            "index_type": "NONCLUSTERED INDEX",
            "partition_number": 1,
            "avg_fragmentation_in_percent": 12.2,
            "page_count": 2000,
        },
        {
            "object_id": 140,
            "index_id": 2,
            "database_name": "Orders",
            "schema_name": "sales",
            "table_name": "Customers",
            "index_name": "IX_Customers_Name",
            "index_type": "NONCLUSTERED INDEX",
            "partition_number": 1,
            "avg_fragmentation_in_percent": 4.9,
            "page_count": 5000,
        },
    ]

    result = list_index_fragmentation(client, database_name="Orders")

    assert [item.index_name for item in result] == [
        "IX_Tiny_Name",
        "IX_OrderItems_Date",
        "IX_Orders_Customer",
        "IX_Customers_Name",
    ]
    assert [item.recommended_action for item in result] == [
        "NONE",
        "REBUILD",
        "REORGANIZE",
        "NONE",
    ]
    assert result[1] == IndexFragmentationItem(
        database_name="Orders",
        schema_name="sales",
        table_name="OrderItems",
        index_name="IX_OrderItems_Date",
        index_type="NONCLUSTERED INDEX",
        partition_number=1,
        avg_fragmentation_in_percent=35.5,
        page_count=5000,
        recommended_action="REBUILD",
        action_enabled=True,
        online_rebuild_supported=False,
        error_message=None,
    )


def test_list_index_fragmentation_collects_all_pages_for_snapshot() -> None:
    client = FakeSqlServerClient("collect-dsn")
    client.fragmentation_targets = [
        {
            "database_name": "Orders",
            "schema_name": "sales",
            "table_name": f"OrderItems{i}",
            "object_id": i,
            "index_id": 2,
            "index_name": f"IX_OrderItems{i}_Date",
        }
        for i in range(1, 502)
    ]
    client.fragmentation_rows = [
        {
            "object_id": i,
            "index_id": 2,
            "database_name": "Orders",
            "schema_name": "sales",
            "table_name": f"OrderItems{i}",
            "index_name": f"IX_OrderItems{i}_Date",
            "index_type": "NONCLUSTERED INDEX",
            "partition_number": 1,
            "avg_fragmentation_in_percent": 10.0,
            "page_count": 2000,
        }
        for i in range(1, 502)
    ]

    result = list_index_fragmentation(client, database_name="Orders")

    assert len(result) == 501
    assert {item.index_name for item in result} >= {"IX_OrderItems1_Date", "IX_OrderItems501_Date"}
    fragmentation_page_queries = [
        parameters
        for sql, parameters in client.queries
        if "dm_db_index_physical_stats" in sql and "ROW_NUMBER() OVER" in sql
    ]
    assert fragmentation_page_queries == [
        ("Orders", "Orders", 1, 500, "Orders"),
        ("Orders", "Orders", 501, 1000, "Orders"),
    ]


def test_get_index_fragmentation_scans_only_requested_page_indexes() -> None:
    instance = _instance()
    session = FakeSession(instance)
    collected_at = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    session.fragmentation_snapshots = [
        IndexFragmentationSnapshot(
            id=uuid.uuid4(),
            instance_id=instance.id,
            database_name="Orders",
            schema_name="sales",
            table_name="OrderItems",
            index_name="IX_OrderItems_Date",
            index_type="NONCLUSTERED INDEX",
            partition_number=1,
            avg_fragmentation_in_percent=35.5,
            page_count=5000,
            recommended_action="REBUILD",
            online_rebuild_supported=True,
            collected_at=collected_at,
        )
    ]
    session.index_statuses = [
        IndexCollectionStatus(
            instance_id=instance.id,
            database_name="Orders",
            index_type="fragmentation",
            status="success",
            last_success_at=collected_at,
            item_count=1,
        )
    ]

    result = asyncio.run(
        get_index_fragmentation(
            session,
            instance.id,
            "Orders",
            page=1,
            page_size=1,
            now=lambda: collected_at + timedelta(seconds=300),
        )
    )

    assert result is not None
    assert result.total == 1
    assert result.checked_at == collected_at
    assert result.collection_status == "success"
    assert result.collection_error is None
    assert result.stale is False
    assert [item.index_name for item in result.items] == ["IX_OrderItems_Date"]


def test_get_index_fragmentation_returns_only_requested_backend_page() -> None:
    instance = _instance()
    session = FakeSession(instance)
    collected_at = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    session.fragmentation_snapshots = [
        IndexFragmentationSnapshot(
            id=uuid.uuid4(),
            instance_id=instance.id,
            database_name="Orders",
            schema_name="sales",
            table_name=f"OrderItems{i}",
            index_name=f"IX_OrderItems{i}_Date",
            index_type="NONCLUSTERED INDEX",
            partition_number=1,
            avg_fragmentation_in_percent=10.0,
            page_count=2000,
            recommended_action="REORGANIZE",
            online_rebuild_supported=True,
            collected_at=collected_at,
        )
        for i in range(1, 1001)
    ]

    result = asyncio.run(
        get_index_fragmentation(
            session,
            instance.id,
            "Orders",
            page=2,
            page_size=20,
            now=lambda: collected_at,
        )
    )

    assert result is not None
    assert result.total == 1000
    assert len(result.items) == 20


def test_get_index_fragmentation_uses_local_snapshots_without_sql_server_client() -> None:
    instance = _instance()
    session = FakeSession(instance)

    def forbidden_client_factory(connection_string: str):
        raise AssertionError("API reads local snapshots and must not connect to SQL Server")

    result = asyncio.run(
        get_index_fragmentation(
            session,
            instance.id,
            "Orders",
            client_factory=forbidden_client_factory,
        )
    )

    assert result is not None
    assert result.items == []


def test_supports_online_index_rebuild_detects_enterprise_or_modern_sql_server() -> None:
    enterprise_client = FakeSqlServerClient("collect-dsn")
    enterprise_client.version_rows = [
        {"engine_edition": 3, "edition": "Enterprise Edition", "product_major_version": 14}
    ]
    standard_2019_client = FakeSqlServerClient("collect-dsn")
    standard_2019_client.version_rows = [
        {"engine_edition": 3, "edition": "Standard Edition", "product_major_version": 15}
    ]
    standard_2016_client = FakeSqlServerClient("collect-dsn")
    standard_2016_client.version_rows = [
        {"engine_edition": 3, "edition": "Standard Edition", "product_major_version": 13}
    ]

    assert supports_online_index_rebuild(enterprise_client) is True
    assert supports_online_index_rebuild(standard_2019_client) is True
    assert supports_online_index_rebuild(standard_2016_client) is False


def test_build_index_maintenance_sql_uses_online_when_supported_for_rebuild() -> None:
    sql = build_index_maintenance_sql(
        database_name="Orders",
        schema_name="sales",
        table_name="OrderItems",
        index_name="IX_OrderItems_Date",
        action="REBUILD",
        online_rebuild=True,
    )

    assert sql == (
        "ALTER INDEX [IX_OrderItems_Date] ON [Orders].[sales].[OrderItems] "
        "REBUILD WITH (ONLINE = ON)"
    )


def test_build_index_maintenance_sql_reorganize_never_uses_online() -> None:
    sql = build_index_maintenance_sql(
        database_name="Orders",
        schema_name="sales",
        table_name="OrderItems",
        index_name="IX_OrderItems_Date",
        action="REORGANIZE",
        online_rebuild=True,
    )

    assert sql == "ALTER INDEX [IX_OrderItems_Date] ON [Orders].[sales].[OrderItems] REORGANIZE"


def test_execute_fragmentation_action_redetects_online_and_writes_audit() -> None:
    instance = _instance()
    session = FakeSession(instance)
    client = FakeSqlServerClient("kill-dsn")
    client.version_rows = [
        {"engine_edition": 3, "edition": "Enterprise Edition", "product_major_version": 14}
    ]

    response = asyncio.run(
        execute_fragmentation_action(
            session,
            FragmentationActionRequestData(
                instance_id=instance.id,
                database_name="Orders",
                schema_name="sales",
                table_name="OrderItems",
                index_name="IX_OrderItems_Date",
                partition_number=1,
                action="REBUILD",
                avg_fragmentation_in_percent=35.5,
                page_count=5000,
            ),
            operator=_operator(),
            client_factory=lambda connection_string: client,
        )
    )

    assert response.result == "running"
    assert response.action == "REBUILD"
    assert response.online_used is True
    assert client.executed == []
    assert session.added[0].action == "REBUILD"
    assert session.added[0].online_used is True
    assert session.added[0].result == "running"
    assert session.added[0].ddl_summary == (
        "ALTER INDEX [IX_OrderItems_Date] ON [Orders].[sales].[OrderItems] "
        "REBUILD WITH (ONLINE = ON)"
    )


def test_execute_fragmentation_action_uses_configured_operation_timeout(monkeypatch) -> None:
    instance = _instance(index_operation_timeout_seconds=1200)
    session = FakeSession(instance)
    audit = MissingIndexStore(
        id=uuid.uuid4(),
        operator_user_id=uuid.uuid4(),
        operator_name="alice",
        instance_id=instance.id,
        database_name="Orders",
        schema_name="sales",
        table_name="OrderItems",
        index_name="IX_OrderItems_Date",
        key_columns=[],
        include_columns=[],
        action="REORGANIZE",
        partition_number=1,
        online_used=False,
        fragmentation_percent=12.2,
        page_count=2000,
        ddl_summary="ALTER INDEX [IX_OrderItems_Date] ON [Orders].[sales].[OrderItems] REORGANIZE",
        result="running",
        error_message=None,
    )
    session.added.append(audit)
    client = FakeSqlServerClient("kill-dsn")

    asyncio.run(run_fragmentation_ddl(session, audit.id, client_factory=lambda _: client))

    assert audit.result == "success"
    assert client.execution_timeouts == [1200]


def test_execute_fragmentation_action_reports_timeout_failure(monkeypatch) -> None:
    instance = _instance(index_operation_timeout_seconds=1200)
    session = FakeSession(instance)
    audit = MissingIndexStore(
        id=uuid.uuid4(),
        operator_user_id=uuid.uuid4(),
        operator_name="alice",
        instance_id=instance.id,
        database_name="Orders",
        schema_name="sales",
        table_name="OrderItems",
        index_name="IX_OrderItems_Date",
        key_columns=[],
        include_columns=[],
        action="REORGANIZE",
        partition_number=1,
        online_used=False,
        fragmentation_percent=12.2,
        page_count=2000,
        ddl_summary="ALTER INDEX [IX_OrderItems_Date] ON [Orders].[sales].[OrderItems] REORGANIZE",
        result="running",
        error_message=None,
    )
    session.added.append(audit)
    client = FakeSqlServerClient("kill-dsn")
    client.execute_exception = RuntimeError("HYT00", "Query timeout expired")

    asyncio.run(run_fragmentation_ddl(session, audit.id, client_factory=lambda _: client))

    assert audit.result == "failed"
    assert audit.error_message == "INDEX_MAINTENANCE_TIMEOUT"
    assert client.execution_timeouts == [1200]


def test_execute_fragmentation_action_falls_back_to_collect_dsn_when_kill_dsn_missing() -> None:
    instance = _instance(encrypted_kill_dsn=None)
    session = FakeSession(instance)
    client = FakeSqlServerClient("collect-dsn")

    response = asyncio.run(
        execute_fragmentation_action(
            session,
            FragmentationActionRequestData(
                instance_id=instance.id,
                database_name="Orders",
                schema_name="sales",
                table_name="OrderItems",
                index_name="IX_OrderItems_Date",
                partition_number=1,
                action="REORGANIZE",
                avg_fragmentation_in_percent=12.2,
                page_count=2000,
            ),
            operator=_operator(),
            client_factory=lambda connection_string: client,
        )
    )

    assert response.result == "running"
    assert client.connection_string == "collect-dsn"
    assert client.executed == []
    assert session.added[0].ddl_summary == (
        "ALTER INDEX [IX_OrderItems_Date] ON [Orders].[sales].[OrderItems] REORGANIZE"
    )
