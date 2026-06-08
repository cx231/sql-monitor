from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.api.deps import current_user, get_db_session
from app.schemas.indexes import IndexCreateResponse, IndexFragmentationActionResponse
from app.services.index_service import IndexFragmentationItem, IndexSnapshotPage, MissingIndexCandidate


class FakeIndexStore:
    def __init__(self):
        self.instance_id = uuid.uuid4()

    async def get(self, model, instance_id):
        return None


def _user(role: str):
    return SimpleNamespace(id=uuid.uuid4(), username=f"{role}_user", role=role, status="active")


def test_missing_index_create_route_requires_dba_or_admin(api_client) -> None:
    app = api_client.app
    app.dependency_overrides[current_user] = lambda: _user("developer")
    app.dependency_overrides[get_db_session] = lambda: FakeIndexStore()

    response = api_client.post(
        "/api/indexes",
        json={
            "instance_id": str(uuid.uuid4()),
            "database_name": "Orders",
            "schema_name": "sales",
            "table_name": "OrderItems",
            "key_columns": ["CustomerId"],
            "include_columns": [],
            "index_name": "IX_OrderItems_CustomerId",
        },
    )

    assert response.status_code == 403
    app.dependency_overrides.clear()


def test_missing_index_create_route_returns_running_and_schedules_background_task(
    api_client,
    monkeypatch,
) -> None:
    app = api_client.app
    instance_id = uuid.uuid4()
    audit_id = uuid.uuid4()
    scheduled: list[uuid.UUID] = []
    app.dependency_overrides[current_user] = lambda: _user("dba")
    app.dependency_overrides[get_db_session] = lambda: FakeIndexStore()

    async def fake_create_missing_index(*args, **kwargs):
        return IndexCreateResponse(
            audit_id=audit_id,
            instance_id=instance_id,
            database_name="Orders",
            schema_name="sales",
            table_name="OrderItems",
            index_name="IX_OrderItems_CustomerId",
            result="running",
            error_message=None,
        )

    async def fake_run_missing_index_ddl_task(task_audit_id):
        scheduled.append(task_audit_id)

    monkeypatch.setattr("app.api.routes.indexes.create_missing_index", fake_create_missing_index)
    monkeypatch.setattr(
        "app.api.routes.indexes._run_missing_index_ddl_task",
        fake_run_missing_index_ddl_task,
    )

    response = api_client.post(
        "/api/indexes",
        json={
            "instance_id": str(instance_id),
            "database_name": "Orders",
            "schema_name": "sales",
            "table_name": "OrderItems",
            "key_columns": ["CustomerId"],
            "include_columns": [],
            "index_name": "IX_OrderItems_CustomerId",
        },
    )

    assert response.status_code == 200
    assert response.json()["result"] == "running"
    assert scheduled == [audit_id]
    app.dependency_overrides.clear()


def test_missing_index_read_routes_allow_developer(api_client, monkeypatch) -> None:
    app = api_client.app
    instance_id = uuid.uuid4()
    app.dependency_overrides[current_user] = lambda: _user("developer")
    app.dependency_overrides[get_db_session] = lambda: FakeIndexStore()

    async def fake_get_user_databases(*args, **kwargs):
        return ["Orders"]

    async def fake_get_missing_indexes(*args, **kwargs):
        return IndexSnapshotPage(
            total=2,
            checked_at=None,
            collection_status="success",
            collection_error=None,
            stale=False,
            items=[
                MissingIndexCandidate(
                    database_name="Orders",
                    schema_name="sales",
                    table_name="Invoices",
                    equality_columns=["OrderId"],
                    inequality_columns=[],
                    include_columns=[],
                    user_seeks=3,
                    user_scans=1,
                    avg_total_user_cost=8.5,
                    avg_user_impact=72.0,
                    recommended_index_name="IX_Invoices_OrderId",
                    create_enabled=True,
                    error_message=None,
                ),
            ],
        )

    monkeypatch.setattr("app.api.routes.indexes.get_user_databases", fake_get_user_databases)
    monkeypatch.setattr(
        "app.api.routes.indexes.get_missing_indexes",
        fake_get_missing_indexes,
    )

    databases_response = api_client.get(f"/api/indexes/databases?instance_id={instance_id}")
    missing_response = api_client.get(
        f"/api/indexes/missing?instance_id={instance_id}&database_name=Orders&page=2&page_size=1"
    )

    assert databases_response.status_code == 200
    assert databases_response.json()["databases"] == ["Orders"]
    assert missing_response.status_code == 200
    assert missing_response.json()["page"] == 2
    assert missing_response.json()["page_size"] == 1
    assert missing_response.json()["total"] == 2
    assert missing_response.json()["collection_status"] == "success"
    assert missing_response.json()["stale"] is False
    assert missing_response.json()["items"][0]["recommended_index_name"] == "IX_Invoices_OrderId"
    app.dependency_overrides.clear()


def test_index_read_routes_default_to_twenty_and_allow_five_hundred(api_client, monkeypatch) -> None:
    app = api_client.app
    instance_id = uuid.uuid4()
    app.dependency_overrides[current_user] = lambda: _user("developer")
    app.dependency_overrides[get_db_session] = lambda: FakeIndexStore()

    async def fake_get_missing_indexes(*args, **kwargs):
        return IndexSnapshotPage(
            items=[],
            total=0,
            checked_at=None,
            collection_status="unknown",
            collection_error=None,
            stale=True,
        )

    async def fake_get_index_fragmentation(*args, **kwargs):
        return IndexSnapshotPage(
            items=[],
            total=0,
            checked_at=None,
            collection_status="unknown",
            collection_error=None,
            stale=True,
        )

    monkeypatch.setattr(
        "app.api.routes.indexes.get_missing_indexes",
        fake_get_missing_indexes,
    )
    monkeypatch.setattr(
        "app.api.routes.indexes.get_index_fragmentation",
        fake_get_index_fragmentation,
        raising=False,
    )

    missing_response = api_client.get(
        f"/api/indexes/missing?instance_id={instance_id}&database_name=Orders"
    )
    fragmentation_response = api_client.get(
        f"/api/indexes/fragmentation?instance_id={instance_id}&database_name=Orders&page_size=500"
    )

    assert missing_response.status_code == 200
    assert missing_response.json()["page_size"] == 20
    assert fragmentation_response.status_code == 200
    assert fragmentation_response.json()["page_size"] == 500
    app.dependency_overrides.clear()


def test_fragmentation_read_route_allows_developer(api_client, monkeypatch) -> None:
    app = api_client.app
    instance_id = uuid.uuid4()
    app.dependency_overrides[current_user] = lambda: _user("developer")
    app.dependency_overrides[get_db_session] = lambda: FakeIndexStore()

    async def fake_get_index_fragmentation(*args, **kwargs):
        return IndexSnapshotPage(
            total=2,
            checked_at=None,
            collection_status="success",
            collection_error=None,
            stale=False,
            items=[
                IndexFragmentationItem(
                    database_name="Orders",
                    schema_name="sales",
                    table_name="Invoices",
                    index_name="IX_Invoices_OrderId",
                    index_type="NONCLUSTERED INDEX",
                    partition_number=1,
                    avg_fragmentation_in_percent=12.0,
                    page_count=2500,
                    recommended_action="REORGANIZE",
                    action_enabled=True,
                    online_rebuild_supported=True,
                    error_message=None,
                ),
            ],
        )

    monkeypatch.setattr(
        "app.api.routes.indexes.get_index_fragmentation",
        fake_get_index_fragmentation,
        raising=False,
    )

    response = api_client.get(
        f"/api/indexes/fragmentation?instance_id={instance_id}&database_name=Orders&page=2&page_size=1"
    )

    assert response.status_code == 200
    assert response.json()["page"] == 2
    assert response.json()["page_size"] == 1
    assert response.json()["total"] == 2
    assert response.json()["collection_status"] == "success"
    assert response.json()["stale"] is False
    assert response.json()["items"][0]["recommended_action"] == "REORGANIZE"
    assert response.json()["items"][0]["online_rebuild_supported"] is True
    app.dependency_overrides.clear()


def test_fragmentation_action_route_requires_dba_or_admin(api_client) -> None:
    app = api_client.app
    app.dependency_overrides[current_user] = lambda: _user("developer")
    app.dependency_overrides[get_db_session] = lambda: FakeIndexStore()

    response = api_client.post(
        "/api/indexes/fragmentation/actions",
        json={
            "instance_id": str(uuid.uuid4()),
            "database_name": "Orders",
            "schema_name": "sales",
            "table_name": "OrderItems",
            "index_name": "IX_OrderItems_Date",
            "partition_number": 1,
            "action": "REBUILD",
            "avg_fragmentation_in_percent": 35.5,
            "page_count": 5000,
        },
    )

    assert response.status_code == 403
    app.dependency_overrides.clear()


def test_fragmentation_action_route_returns_running_and_schedules_background_task(
    api_client,
    monkeypatch,
) -> None:
    app = api_client.app
    instance_id = uuid.uuid4()
    audit_id = uuid.uuid4()
    scheduled: list[uuid.UUID] = []
    app.dependency_overrides[current_user] = lambda: _user("dba")
    app.dependency_overrides[get_db_session] = lambda: FakeIndexStore()

    async def fake_execute_fragmentation_action(*args, **kwargs):
        return IndexFragmentationActionResponse(
            audit_id=audit_id,
            instance_id=instance_id,
            database_name="Orders",
            schema_name="sales",
            table_name="OrderItems",
            index_name="IX_OrderItems_Date",
            partition_number=1,
            action="REORGANIZE",
            online_used=False,
            result="running",
            error_message=None,
        )

    async def fake_run_fragmentation_ddl_task(task_audit_id):
        scheduled.append(task_audit_id)

    monkeypatch.setattr(
        "app.api.routes.indexes.execute_fragmentation_action",
        fake_execute_fragmentation_action,
    )
    monkeypatch.setattr(
        "app.api.routes.indexes._run_fragmentation_ddl_task",
        fake_run_fragmentation_ddl_task,
    )

    response = api_client.post(
        "/api/indexes/fragmentation/actions",
        json={
            "instance_id": str(instance_id),
            "database_name": "Orders",
            "schema_name": "sales",
            "table_name": "OrderItems",
            "index_name": "IX_OrderItems_Date",
            "partition_number": 1,
            "action": "REORGANIZE",
            "avg_fragmentation_in_percent": 12.2,
            "page_count": 2000,
        },
    )

    assert response.status_code == 200
    assert response.json()["result"] == "running"
    assert scheduled == [audit_id]
    app.dependency_overrides.clear()
