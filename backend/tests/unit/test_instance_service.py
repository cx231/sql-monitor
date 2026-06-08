from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from app.api.deps import current_user, get_db_session
from app.db.models import Instance, InstanceCollectStatus
from app.schemas.instances import InstanceConnectionTestRequest, InstanceCreate, InstanceUpdate
from app.services.instance_service import (
    CONNECTION_TEST_SQL,
    build_sql_auth_connection_string,
    delete_instance,
    decrypt_connection_string,
    encrypt_connection_string,
    list_instances,
    create_instance,
    test_existing_instance_connection as run_existing_instance_connection_test,
    test_new_instance_connection as run_new_instance_connection_test,
    update_instance,
)


def _fake_user(role: str):
    return SimpleNamespace(
        id=uuid.uuid4(),
        username=f"{role}_user",
        password_hash="hash",
        role=role,
        status="active",
    )


def test_connection_string_encrypt_decrypt_round_trip() -> None:
    original = "Driver={ODBC Driver 18 for SQL Server};Server=db.example.com,1433;Database=sqlmon;"

    encrypted = encrypt_connection_string(original)
    decrypted = decrypt_connection_string(encrypted)

    assert encrypted != original
    assert decrypted == original


def test_build_sql_auth_connection_string_uses_sql_auth_fields(monkeypatch) -> None:
    fake_pyodbc = SimpleNamespace(drivers=lambda: ["ODBC Driver 18 for SQL Server"])
    monkeypatch.setitem(sys.modules, "pyodbc", fake_pyodbc)

    dsn = build_sql_auth_connection_string(
        host="10.0.8.12",
        port=1433,
        username="sqlmon_user",
        password="p;a}s",
        database_name="Orders",
    )

    assert "Driver={ODBC Driver 18 for SQL Server}" in dsn
    assert "Server={10.0.8.12,1433}" in dsn
    assert "Database={Orders}" in dsn
    assert "UID={sqlmon_user}" in dsn
    assert "PWD={p;a}}s}" in dsn
    assert "TrustServerCertificate=yes" in dsn


def test_build_sql_auth_connection_string_uses_installed_sql_server_driver(monkeypatch) -> None:
    fake_pyodbc = SimpleNamespace(drivers=lambda: ["ODBC Driver 17 for SQL Server"])
    monkeypatch.setitem(sys.modules, "pyodbc", fake_pyodbc)

    dsn = build_sql_auth_connection_string(
        host="10.0.8.12",
        port=1433,
        username="sqlmon_user",
        password="secret-password",
        database_name="master",
    )

    assert "Driver={ODBC Driver 17 for SQL Server}" in dsn


def test_connection_test_sql_returns_concise_version() -> None:
    assert "@@VERSION" not in CONNECTION_TEST_SQL
    assert "SERVERPROPERTY('ProductVersion')" in CONNECTION_TEST_SQL
    assert "SERVERPROPERTY('Edition')" in CONNECTION_TEST_SQL


def test_new_instance_connection_test_returns_sanitized_success() -> None:
    calls = []

    class FakeSqlServerClient:
        def __init__(self, connection_string):
            calls.append(connection_string)

        def query(self, sql, timeout_seconds=None):
            calls.append((sql, timeout_seconds))
            return [
                {
                    "sqlserver_version": "SQL Server 2022 CU",
                    "database_name": "master",
                    "available_database_name": None,
                },
                {
                    "sqlserver_version": None,
                    "database_name": None,
                    "available_database_name": "master",
                },
                {
                    "sqlserver_version": None,
                    "database_name": None,
                    "available_database_name": "Orders",
                }
            ]

    payload = InstanceConnectionTestRequest(
        host="10.0.8.12",
        port=1433,
        username="sqlmon_user",
        password="secret-password",
    )

    result = run_new_instance_connection_test(payload, client_factory=FakeSqlServerClient)

    assert result.success is True
    assert result.sqlserver_version == "SQL Server 2022 CU"
    assert result.database_name == "master"
    assert result.databases == ["master", "Orders"]
    assert result.error_message is None
    assert "secret-password" not in result.model_dump_json()
    assert "secret-password" in calls[0]


def test_new_instance_connection_test_returns_sanitized_failure() -> None:
    class FakeSqlServerClient:
        def __init__(self, connection_string):
            self.connection_string = connection_string

        def query(self, sql, timeout_seconds=None):
            raise RuntimeError("Login failed for user sqlmon_user with password secret-password")

    payload = InstanceConnectionTestRequest(
        host="10.0.8.12",
        port=1433,
        username="sqlmon_user",
        password="secret-password",
    )

    result = run_new_instance_connection_test(payload, client_factory=FakeSqlServerClient)

    assert result.success is False
    assert result.sqlserver_version is None
    assert result.database_name is None
    assert result.error_message == "连接测试失败"
    assert "secret-password" not in result.model_dump_json()


def test_existing_instance_connection_test_uses_stored_encrypted_dsn() -> None:
    instance = Instance(
        id=uuid.uuid4(),
        name="核心库",
        host="10.0.8.12",
        port=1433,
        database_name=None,
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("stored-dsn"),
        encrypted_kill_dsn=None,
        status="disabled",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version=None,
    )
    calls = []

    class FakeSession:
        def __init__(self):
            self.committed = False
            self.refreshed = []

        async def get(self, model, instance_id):
            return instance

        async def commit(self):
            self.committed = True

        async def refresh(self, obj):
            self.refreshed.append(obj)

    class FakeSqlServerClient:
        def __init__(self, connection_string):
            calls.append(connection_string)

        def query(self, sql, timeout_seconds=None):
            return [{"sqlserver_version": "SQL Server 2019", "database_name": "master"}]

    fake_session = FakeSession()
    result = asyncio.run(
        run_existing_instance_connection_test(
            fake_session,
            instance.id,
            client_factory=FakeSqlServerClient,
        )
    )

    assert result is not None
    assert result.success is True
    assert result.sqlserver_version == "SQL Server 2019"
    assert calls == ["stored-dsn"]
    assert instance.sqlserver_version == "SQL Server 2019"
    assert instance.database_name == "master"
    assert fake_session.committed is True
    assert fake_session.refreshed == [instance]


def test_existing_instance_connection_test_updates_instance_metadata_on_success() -> None:
    instance = Instance(
        id=uuid.uuid4(),
        name="核心库",
        host="10.0.8.12",
        port=1433,
        database_name="master",
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("stored-dsn"),
        encrypted_kill_dsn=None,
        status="disabled",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version="SQL Server 2017",
    )

    class FakeSession:
        def __init__(self):
            self.committed = False
            self.refreshed = []

        async def get(self, model, instance_id):
            return instance

        async def commit(self):
            self.committed = True

        async def refresh(self, obj):
            self.refreshed.append(obj)

    class FakeSqlServerClient:
        def __init__(self, connection_string):
            self.connection_string = connection_string

        def query(self, sql, timeout_seconds=None):
            return [
                {
                    "sqlserver_version": "SQL Server 2022 CU",
                    "database_name": "Orders",
                    "available_database_name": None,
                },
                {
                    "sqlserver_version": None,
                    "database_name": None,
                    "available_database_name": "master",
                },
                {
                    "sqlserver_version": None,
                    "database_name": None,
                    "available_database_name": "Orders",
                },
            ]

    fake_session = FakeSession()
    result = asyncio.run(
        run_existing_instance_connection_test(
            fake_session,
            instance.id,
            client_factory=FakeSqlServerClient,
        )
    )

    assert result is not None
    assert result.success is True
    assert result.sqlserver_version == "SQL Server 2022 CU"
    assert result.database_name == "Orders"
    assert result.databases == ["master", "Orders"]
    assert result.instance is not None
    assert result.instance.sqlserver_version == "SQL Server 2022 CU"
    assert result.instance.database_name == "Orders"
    assert result.instance.status == "online"
    assert instance.sqlserver_version == "SQL Server 2022 CU"
    assert instance.database_name == "Orders"
    assert instance.status == "online"
    assert fake_session.committed is True
    assert fake_session.refreshed == [instance]


def test_existing_instance_connection_test_preserves_metadata_on_failure() -> None:
    instance = Instance(
        id=uuid.uuid4(),
        name="核心库",
        host="10.0.8.12",
        port=1433,
        database_name="Orders",
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("stored-dsn"),
        encrypted_kill_dsn=None,
        status="disabled",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version="SQL Server 2019",
    )

    class FakeSession:
        def __init__(self):
            self.committed = False
            self.refreshed = []

        async def get(self, model, instance_id):
            return instance

        async def commit(self):
            self.committed = True

        async def refresh(self, obj):
            self.refreshed.append(obj)

    class FakeSqlServerClient:
        def __init__(self, connection_string):
            self.connection_string = connection_string

        def query(self, sql, timeout_seconds=None):
            raise RuntimeError("connection failed")

    fake_session = FakeSession()
    result = asyncio.run(
        run_existing_instance_connection_test(
            fake_session,
            instance.id,
            client_factory=FakeSqlServerClient,
        )
    )

    assert result is not None
    assert result.success is False
    assert result.instance is not None
    assert result.instance.status == "offline"
    assert instance.sqlserver_version == "SQL Server 2019"
    assert instance.database_name == "Orders"
    assert instance.status == "offline"
    assert fake_session.committed is True
    assert fake_session.refreshed == [instance]


def test_existing_instance_connection_test_returns_none_for_missing_instance() -> None:
    class FakeSession:
        async def get(self, model, instance_id):
            return None

    result = asyncio.run(
        run_existing_instance_connection_test(
            FakeSession(),
            uuid.uuid4(),
            client_factory=lambda connection_string: None,
        )
    )

    assert result is None


def test_create_instance_encrypts_connection_string_and_creates_collect_status() -> None:
    payload = InstanceCreate(
        name="核心库",
        host="db.example.com",
        port=1433,
        database_name="sqlmon",
        environment="prod",
        collect_dsn="Driver={ODBC Driver 18 for SQL Server};Server=db.example.com,1433;Database=sqlmon;",
        kill_dsn="Driver={ODBC Driver 18 for SQL Server};Server=db.example.com,1433;Database=sqlmon;",
        status="disabled",
        collect_interval_seconds=30,
        missing_index_collect_interval_seconds=600,
        index_fragmentation_collect_interval_seconds=900,
        index_operation_timeout_seconds=2400,
        retention_days=14,
        business_owner="业务负责人",
        dba_owner="DBA",
        sqlserver_version="SQL Server 2022",
    )

    class FakeSession:
        def __init__(self):
            self.added = []
            self.committed = False
            self.refreshed = []

        def add(self, obj):
            self.added.append(obj)

        async def commit(self):
            self.committed = True

        async def refresh(self, obj):
            self.refreshed.append(obj)

    result = asyncio.run(create_instance(FakeSession(), payload))

    assert result.name == payload.name
    assert result.has_collect_dsn is True
    assert result.has_kill_dsn is True
    assert not hasattr(result, "collect_dsn")
    assert not hasattr(result, "kill_dsn")
    assert result.status == payload.status
    assert result.missing_index_collect_interval_seconds == 600
    assert result.index_fragmentation_collect_interval_seconds == 900
    assert result.index_operation_timeout_seconds == 2400
    assert result.id is not None

    fake_session = FakeSession()
    asyncio.run(create_instance(fake_session, payload))
    assert len(fake_session.added) == 2
    stored_instance = fake_session.added[0]
    stored_status = fake_session.added[1]
    assert stored_instance.encrypted_collect_dsn != payload.collect_dsn
    assert stored_instance.encrypted_kill_dsn != payload.kill_dsn
    assert stored_status.instance_id == stored_instance.id
    assert stored_status.status == "unknown"


def test_create_instance_builds_collect_dsn_from_sql_auth_fields(monkeypatch) -> None:
    fake_pyodbc = SimpleNamespace(drivers=lambda: ["ODBC Driver 17 for SQL Server"])
    monkeypatch.setitem(sys.modules, "pyodbc", fake_pyodbc)
    payload = InstanceCreate(
        name="核心库",
        host="192.168.1.26",
        port=1433,
        database_name="master",
        username="sa",
        password="secret-password",
        status="offline",
    )

    class FakeSession:
        def __init__(self):
            self.added = []

        def add(self, obj):
            self.added.append(obj)

        async def commit(self):
            return None

        async def refresh(self, obj):
            return None

    fake_session = FakeSession()

    asyncio.run(create_instance(fake_session, payload))

    stored_instance = fake_session.added[0]
    collect_dsn = decrypt_connection_string(stored_instance.encrypted_collect_dsn)
    assert "Driver={ODBC Driver 17 for SQL Server}" in collect_dsn
    assert "Server={192.168.1.26,1433}" in collect_dsn
    assert "Database={master}" in collect_dsn
    assert "UID={sa}" in collect_dsn
    assert "PWD={secret-password}" in collect_dsn


def test_list_instances_returns_instances_sorted_by_created_at_desc() -> None:
    newer = Instance(
        id=uuid.uuid4(),
        name="newer",
        host="db2",
        port=1433,
        database_name=None,
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("dsn-2"),
        encrypted_kill_dsn=None,
        status="online",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version=None,
    )
    older = Instance(
        id=uuid.uuid4(),
        name="older",
        host="db1",
        port=1433,
        database_name=None,
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("dsn-1"),
        encrypted_kill_dsn=None,
        status="offline",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version=None,
    )
    newer.created_at = datetime.now(timezone.utc)
    older.created_at = datetime.now(timezone.utc)

    class FakeResult:
        def __init__(self, items):
            self._items = items

        def scalars(self):
            return self

        def all(self):
            return self._items

    class FakeSession:
        async def execute(self, statement):
            return FakeResult([newer, older])

    result = asyncio.run(list_instances(FakeSession()))

    assert [item.name for item in result] == ["newer", "older"]
    assert result[0].has_collect_dsn is True
    assert result[1].has_collect_dsn is True
    assert not hasattr(result[0], "collect_dsn")
    assert not hasattr(result[1], "collect_dsn")


def test_list_instances_includes_collect_status_for_staleness_diagnosis() -> None:
    instance_id = uuid.uuid4()
    instance = Instance(
        id=instance_id,
        name="prod",
        host="db1",
        port=1433,
        database_name=None,
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("dsn-1"),
        encrypted_kill_dsn=None,
        status="collect_error",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version=None,
    )
    collect_status = InstanceCollectStatus(
        instance_id=instance_id,
        last_success_at=datetime(2026, 5, 14, 8, 0, tzinfo=timezone.utc),
        last_failure_at=datetime(2026, 5, 14, 8, 5, tzinfo=timezone.utc),
        last_duration_ms=1234,
        consecutive_failures=3,
        status="failed",
        error_message="采集失败",
    )

    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return [instance]

    class FakeSession:
        async def execute(self, statement):
            return FakeResult()

        async def get(self, model, key):
            assert model is InstanceCollectStatus
            assert key == instance_id
            return collect_status

    result = asyncio.run(list_instances(FakeSession()))

    assert result[0].collect_status == "failed"
    assert result[0].last_success_at == datetime(2026, 5, 14, 8, 0, tzinfo=timezone.utc)
    assert result[0].last_failure_at == datetime(2026, 5, 14, 8, 5, tzinfo=timezone.utc)
    assert result[0].last_duration_ms == 1234
    assert result[0].consecutive_failures == 3
    assert result[0].collect_error_message == "采集失败"


def test_list_instances_hides_disabled_instances() -> None:
    active = Instance(
        id=uuid.uuid4(),
        name="active",
        host="db1",
        port=1433,
        database_name=None,
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("dsn-1"),
        encrypted_kill_dsn=None,
        status="online",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version=None,
    )
    disabled = Instance(
        id=uuid.uuid4(),
        name="disabled",
        host="db2",
        port=1433,
        database_name=None,
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("dsn-2"),
        encrypted_kill_dsn=None,
        status="disabled",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version=None,
    )

    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return [active, disabled]

    class FakeSession:
        async def execute(self, statement):
            return FakeResult()

    result = asyncio.run(list_instances(FakeSession()))

    assert [item.name for item in result] == ["active"]


def test_list_instances_route_requires_authentication(api_client) -> None:
    response = api_client.get("/api/instances")

    assert response.status_code == 401


def test_list_instances_route_allows_authenticated_user(api_client) -> None:
    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return []

    class FakeSession:
        async def execute(self, statement):
            return FakeResult()

    app = api_client.app
    app.dependency_overrides[get_db_session] = lambda: FakeSession()
    app.dependency_overrides[current_user] = lambda: _fake_user("viewer")

    response = api_client.get("/api/instances")

    assert response.status_code == 200
    assert response.json() == []
    app.dependency_overrides.clear()


def test_update_instance_updates_connection_strings_without_exposing_ciphertext() -> None:
    instance = Instance(
        id=uuid.uuid4(),
        name="old",
        host="db1",
        port=1433,
        database_name=None,
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("old-dsn"),
        encrypted_kill_dsn=None,
        status="disabled",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version=None,
    )
    payload = InstanceUpdate(
        name="new",
        host="db2",
        port=1500,
        database_name="sqlmon",
        environment="test",
        collect_dsn="new-dsn",
        kill_dsn=None,
        status="offline",
        collect_interval_seconds=10,
        missing_index_collect_interval_seconds=1200,
        index_fragmentation_collect_interval_seconds=1800,
        index_operation_timeout_seconds=3600,
        retention_days=30,
        business_owner="owner",
        dba_owner="dba",
        sqlserver_version="SQL Server 2019",
    )

    class FakeSession:
        def __init__(self):
            self.committed = False
            self.refreshed = []

        async def get(self, model, instance_id):
            return instance

        async def commit(self):
            self.committed = True

        async def refresh(self, obj):
            self.refreshed.append(obj)

    result = asyncio.run(update_instance(FakeSession(), instance.id, payload))

    assert result.name == "new"
    assert result.has_collect_dsn is True
    assert result.has_kill_dsn is False
    assert not hasattr(result, "collect_dsn")
    assert not hasattr(result, "kill_dsn")
    assert result.status == "offline"
    assert result.missing_index_collect_interval_seconds == 1200
    assert result.index_fragmentation_collect_interval_seconds == 1800
    assert result.index_operation_timeout_seconds == 3600
    assert instance.encrypted_collect_dsn != "new-dsn"


def test_create_instance_defaults_index_collection_intervals_to_ten_minutes() -> None:
    payload = InstanceCreate(
        name="核心库",
        host="192.168.1.26",
        database_name="master",
        username="sa",
        password="secret-password",
        status="offline",
    )

    class FakeSession:
        def __init__(self):
            self.added = []

        def add(self, obj):
            self.added.append(obj)

        async def commit(self):
            return None

        async def refresh(self, obj):
            return None

    fake_session = FakeSession()

    result = asyncio.run(create_instance(fake_session, payload))

    stored_instance = fake_session.added[0]
    assert stored_instance.missing_index_collect_interval_seconds == 600
    assert stored_instance.index_fragmentation_collect_interval_seconds == 600
    assert stored_instance.index_operation_timeout_seconds == 1800
    assert result.missing_index_collect_interval_seconds == 600
    assert result.index_fragmentation_collect_interval_seconds == 600
    assert result.index_operation_timeout_seconds == 1800


def test_update_instance_preserves_kill_dsn_when_not_provided() -> None:
    instance = Instance(
        id=uuid.uuid4(),
        name="old",
        host="db1",
        port=1433,
        database_name=None,
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("old-dsn"),
        encrypted_kill_dsn=encrypt_connection_string("old-kill-dsn"),
        status="disabled",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version=None,
    )
    payload = InstanceUpdate(
        name="new",
        host="db2",
        port=1500,
        database_name="sqlmon",
        environment="test",
        status="offline",
        collect_interval_seconds=10,
        retention_days=30,
        business_owner="owner",
        dba_owner="dba",
        sqlserver_version="SQL Server 2019",
    )

    class FakeSession:
        async def get(self, model, instance_id):
            return instance

        async def commit(self):
            return None

        async def refresh(self, obj):
            return None

    result = asyncio.run(update_instance(FakeSession(), instance.id, payload))

    assert result is not None
    assert instance.encrypted_kill_dsn == encrypt_connection_string("old-kill-dsn")
    assert result.has_kill_dsn is True
    assert instance.encrypted_collect_dsn == encrypt_connection_string("old-dsn")


def test_update_instance_clears_kill_dsn_when_explicitly_null() -> None:
    instance = Instance(
        id=uuid.uuid4(),
        name="old",
        host="db1",
        port=1433,
        database_name=None,
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("old-dsn"),
        encrypted_kill_dsn=encrypt_connection_string("old-kill-dsn"),
        status="disabled",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version=None,
    )
    payload = InstanceUpdate(
        name="new",
        host="db2",
        port=1500,
        database_name="sqlmon",
        environment="test",
        collect_dsn="new-dsn",
        kill_dsn=None,
        status="offline",
        collect_interval_seconds=10,
        retention_days=30,
        business_owner="owner",
        dba_owner="dba",
        sqlserver_version="SQL Server 2019",
    )

    class FakeSession:
        async def get(self, model, instance_id):
            return instance

        async def commit(self):
            return None

        async def refresh(self, obj):
            return None

    result = asyncio.run(update_instance(FakeSession(), instance.id, payload))

    assert result is not None
    assert instance.encrypted_kill_dsn is None
    assert result.has_kill_dsn is False


def test_update_instance_only_updates_provided_fields() -> None:
    instance = Instance(
        id=uuid.uuid4(),
        name="old",
        host="db1",
        port=1433,
        database_name="old_db",
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("old-dsn"),
        encrypted_kill_dsn=encrypt_connection_string("old-kill-dsn"),
        status="disabled",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner="old-owner",
        dba_owner="old-dba",
        sqlserver_version="SQL Server 2017",
    )
    payload = InstanceUpdate(name="new")

    class FakeSession:
        async def get(self, model, instance_id):
            return instance

        async def commit(self):
            return None

        async def refresh(self, obj):
            return None

    result = asyncio.run(update_instance(FakeSession(), instance.id, payload))

    assert result is not None
    assert instance.name == "new"
    assert instance.host == "db1"
    assert instance.encrypted_collect_dsn == encrypt_connection_string("old-dsn")
    assert instance.encrypted_kill_dsn == encrypt_connection_string("old-kill-dsn")


def test_delete_instance_soft_disables_instance_without_removing_history() -> None:
    instance_id = uuid.uuid4()
    instance = Instance(
        id=instance_id,
        name="核心库",
        host="10.0.8.12",
        port=1433,
        database_name=None,
        environment="prod",
        encrypted_collect_dsn=encrypt_connection_string("dsn"),
        encrypted_kill_dsn=None,
        status="online",
        collect_interval_seconds=5,
        retention_days=7,
        business_owner=None,
        dba_owner=None,
        sqlserver_version=None,
    )

    class FakeSession:
        def __init__(self):
            self.deleted = []
            self.committed = False
            self.refreshed = []

        async def get(self, model, requested_id):
            assert model is Instance
            return instance

        async def delete(self, obj):
            self.deleted.append(obj)

        async def commit(self):
            self.committed = True

        async def refresh(self, obj):
            self.refreshed.append(obj)

    fake_session = FakeSession()

    result = asyncio.run(delete_instance(fake_session, instance_id))

    assert result is True
    assert instance.status == "disabled"
    assert fake_session.deleted == []
    assert fake_session.committed is True
    assert fake_session.refreshed == [instance]


def test_delete_instance_returns_false_when_missing() -> None:
    class FakeSession:
        async def get(self, model, requested_id):
            return None

        async def delete(self, obj):
            raise AssertionError("delete should not be called")

        async def commit(self):
            raise AssertionError("commit should not be called")

    result = asyncio.run(delete_instance(FakeSession(), uuid.uuid4()))

    assert result is False


def test_instance_update_rejects_invalid_status() -> None:
    with pytest.raises(Exception):
        InstanceUpdate(
            name="new",
            host="db2",
            port=1500,
            database_name="sqlmon",
            environment="test",
            collect_dsn="new-dsn",
            kill_dsn=None,
            status="broken",
            collect_interval_seconds=10,
            retention_days=30,
            business_owner="owner",
            dba_owner="dba",
            sqlserver_version="SQL Server 2019",
        )


def test_instance_create_rejects_invalid_status() -> None:
    with pytest.raises(Exception):
        InstanceCreate(
            name="核心库",
            host="db.example.com",
            collect_dsn="dsn",
            status="broken",
        )


def test_create_instance_route_requires_admin(api_client) -> None:
    app = api_client.app
    app.dependency_overrides[get_db_session] = lambda: None
    app.dependency_overrides[current_user] = lambda: _fake_user("dba")

    response = api_client.post(
        "/api/instances",
        json={
            "name": "核心库",
            "host": "db.example.com",
            "collect_dsn": "dsn",
        },
    )

    assert response.status_code == 403
    app.dependency_overrides.clear()


def test_update_instance_route_requires_admin(api_client) -> None:
    app = api_client.app
    app.dependency_overrides[get_db_session] = lambda: None
    app.dependency_overrides[current_user] = lambda: _fake_user("viewer")

    response = api_client.put(
        f"/api/instances/{uuid.uuid4()}",
        json={
            "name": "核心库",
            "host": "db.example.com",
            "port": 1433,
            "database_name": None,
            "environment": "prod",
            "collect_dsn": "dsn",
            "kill_dsn": None,
            "status": "disabled",
            "collect_interval_seconds": 5,
            "retention_days": 7,
            "business_owner": None,
            "dba_owner": None,
            "sqlserver_version": None,
        },
    )

    assert response.status_code == 403
    app.dependency_overrides.clear()


def test_delete_instance_route_requires_admin(api_client) -> None:
    app = api_client.app
    app.dependency_overrides[get_db_session] = lambda: None
    app.dependency_overrides[current_user] = lambda: _fake_user("viewer")

    response = api_client.delete(f"/api/instances/{uuid.uuid4()}")

    assert response.status_code == 403
    app.dependency_overrides.clear()


def test_new_connection_test_route_requires_admin(api_client) -> None:
    app = api_client.app
    app.dependency_overrides[get_db_session] = lambda: None
    app.dependency_overrides[current_user] = lambda: _fake_user("dba")

    response = api_client.post(
        "/api/instances/test-connection",
        json={
            "host": "10.0.8.12",
            "port": 1433,
            "username": "sqlmon_user",
            "password": "secret-password",
        },
    )

    assert response.status_code == 403
    app.dependency_overrides.clear()


def test_existing_connection_test_route_requires_admin(api_client) -> None:
    app = api_client.app
    app.dependency_overrides[get_db_session] = lambda: None
    app.dependency_overrides[current_user] = lambda: _fake_user("viewer")

    response = api_client.post(f"/api/instances/{uuid.uuid4()}/test-connection")

    assert response.status_code == 403
    app.dependency_overrides.clear()


def test_delete_instance_route_returns_not_found(api_client) -> None:
    class FakeSession:
        async def get(self, model, requested_id):
            return None

    app = api_client.app
    app.dependency_overrides[get_db_session] = lambda: FakeSession()
    app.dependency_overrides[current_user] = lambda: _fake_user("admin")

    response = api_client.delete(f"/api/instances/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "实例不存在"
    app.dependency_overrides.clear()


def test_existing_connection_test_route_returns_not_found(api_client) -> None:
    class FakeSession:
        async def get(self, model, requested_id):
            return None

    app = api_client.app
    app.dependency_overrides[get_db_session] = lambda: FakeSession()
    app.dependency_overrides[current_user] = lambda: _fake_user("admin")

    response = api_client.post(f"/api/instances/{uuid.uuid4()}/test-connection")

    assert response.status_code == 404
    assert response.json()["detail"] == "实例不存在"
    app.dependency_overrides.clear()
