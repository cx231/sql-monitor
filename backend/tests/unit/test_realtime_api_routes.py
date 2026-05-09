from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.deps import current_user, get_db_session
from app.collector.mock_data import build_mock_frame


class FakeSnapshotRepository:
    def __init__(self, frame=None):
        self.frame = frame

    async def get_latest_frame(self, instance_id):
        if self.frame is None or self.frame.instance_id != instance_id:
            return None
        return self.frame

    async def get_frame_before(self, instance_id, target_time, max_delay_seconds):
        if self.frame is None or self.frame.instance_id != instance_id:
            return None
        if self.frame.snapshot_time > target_time:
            return None
        if (target_time - self.frame.snapshot_time).total_seconds() > max_delay_seconds:
            return None
        return self.frame


def _fake_user():
    return SimpleNamespace(id=uuid.uuid4(), username="viewer", role="viewer", status="active")


def _blocking_row(edge):
    return SimpleNamespace(
        root_session_id=edge.root_session_id,
        blocking_session_id=edge.blocker_session_id,
        blocked_session_id=edge.blocked_session_id,
        chain_depth=edge.chain_depth,
        blocked_count=1,
        max_wait_time_ms=edge.wait_duration_ms,
        wait_type=edge.wait_type,
        resource_description=edge.resource_description,
        cycle_detected=edge.cycle_detected,
        special_blocker_code=None,
    )


def _frame(instance_id):
    raw = build_mock_frame(
        instance_id=instance_id,
        snapshot_time=datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc),
    )
    return SimpleNamespace(
        frame_id=raw.frame_id,
        instance_id=raw.instance_id,
        snapshot_time=raw.snapshot_time,
        collect_duration_ms=raw.collect_duration_ms,
        status=raw.status,
        sessions=list(raw.sessions),
        requests=list(raw.requests),
        waits=list(raw.waits),
        blocking_rows=[_blocking_row(edge) for edge in raw.blocking_edges],
    )


def _install_overrides(api_client, repository):
    app = api_client.app
    app.dependency_overrides[get_db_session] = lambda: repository
    app.dependency_overrides[current_user] = _fake_user
    return app


def test_realtime_routes_require_authentication(api_client) -> None:
    instance_id = uuid.uuid4()

    response = api_client.get(f"/api/dashboard?instance_id={instance_id}")

    assert response.status_code == 401


def test_dashboard_route_returns_latest_dashboard(api_client) -> None:
    instance_id = uuid.uuid4()
    app = _install_overrides(api_client, FakeSnapshotRepository(_frame(instance_id)))

    response = api_client.get(f"/api/dashboard?instance_id={instance_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["instance_id"] == str(instance_id)
    assert body["metrics"]["session_count"] == 4
    assert body["metrics"]["active_request_count"] == 2
    app.dependency_overrides.clear()


def test_dashboard_route_returns_clear_error_without_latest_frame(api_client) -> None:
    instance_id = uuid.uuid4()
    app = _install_overrides(api_client, FakeSnapshotRepository())

    response = api_client.get(f"/api/dashboard?instance_id={instance_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "LATEST_FRAME_NOT_FOUND"
    app.dependency_overrides.clear()


def test_sessions_routes_list_and_fetch_single_session(api_client) -> None:
    instance_id = uuid.uuid4()
    app = _install_overrides(api_client, FakeSnapshotRepository(_frame(instance_id)))

    list_response = api_client.get(f"/api/sessions?instance_id={instance_id}&only_blocked=true")
    detail_response = api_client.get(f"/api/sessions/54?instance_id={instance_id}")

    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert detail_response.status_code == 200
    assert detail_response.json()["session_id"] == 54
    assert detail_response.json()["blocking_session_id"] == 53
    app.dependency_overrides.clear()


def test_session_detail_returns_not_found_when_session_missing(api_client) -> None:
    instance_id = uuid.uuid4()
    app = _install_overrides(api_client, FakeSnapshotRepository(_frame(instance_id)))

    response = api_client.get(f"/api/sessions/999?instance_id={instance_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "SESSION_NOT_FOUND"
    app.dependency_overrides.clear()


def test_sql_routes_list_and_fetch_single_sql(api_client) -> None:
    instance_id = uuid.uuid4()
    app = _install_overrides(api_client, FakeSnapshotRepository(_frame(instance_id)))

    list_response = api_client.get(f"/api/sqls?instance_id={instance_id}&sort_by=wait_time_ms")
    sql_hash = list_response.json()["items"][0]["sql_hash"]
    detail_response = api_client.get(f"/api/sqls/{sql_hash}?instance_id={instance_id}")

    assert list_response.status_code == 200
    assert list_response.json()["total"] == 2
    assert detail_response.status_code == 200
    assert detail_response.json()["sql_hash"] == sql_hash
    app.dependency_overrides.clear()


def test_sql_detail_returns_not_found_when_hash_missing(api_client) -> None:
    instance_id = uuid.uuid4()
    app = _install_overrides(api_client, FakeSnapshotRepository(_frame(instance_id)))

    response = api_client.get(f"/api/sqls/missing-hash?instance_id={instance_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "SQL_NOT_FOUND"
    app.dependency_overrides.clear()


def test_blocking_route_returns_chains(api_client) -> None:
    instance_id = uuid.uuid4()
    app = _install_overrides(api_client, FakeSnapshotRepository(_frame(instance_id)))

    response = api_client.get(f"/api/blocking?instance_id={instance_id}")

    assert response.status_code == 200
    assert response.json()["chains"][0]["root_session_id"] == 53
    app.dependency_overrides.clear()


def test_replay_route_returns_frame_near_requested_time(api_client) -> None:
    instance_id = uuid.uuid4()
    frame = _frame(instance_id)
    app = _install_overrides(api_client, FakeSnapshotRepository(frame))

    response = api_client.get(f"/api/replay?instance_id={instance_id}&time=2026-05-10T12:00:02Z")

    assert response.status_code == 200
    body = response.json()
    assert body["instance_id"] == str(instance_id)
    assert body["frame_id"] == str(frame.frame_id)
    assert len(body["sessions"]) == 4
    app.dependency_overrides.clear()


def test_replay_route_returns_clear_error_without_matching_frame(api_client) -> None:
    instance_id = uuid.uuid4()
    app = _install_overrides(api_client, FakeSnapshotRepository())

    response = api_client.get(f"/api/replay?instance_id={instance_id}&time=2026-05-10T12:00:02Z")

    assert response.status_code == 409
    assert response.json()["detail"] == "REPLAY_FRAME_NOT_FOUND"
    app.dependency_overrides.clear()
