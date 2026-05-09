from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from app.api.deps import current_user, get_db_session
from app.db.models import Instance
from app.schemas.instances import InstanceCreate, InstanceUpdate
from app.services.instance_service import (
    decrypt_connection_string,
    encrypt_connection_string,
    list_instances,
    create_instance,
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
        status="disabled",
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
        status="disabled",
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
    assert instance.encrypted_collect_dsn != "new-dsn"


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
