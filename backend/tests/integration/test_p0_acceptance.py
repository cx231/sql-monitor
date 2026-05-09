from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.deps import current_user, get_db_session


class FakeP0Repository:
    def __init__(self):
        self.success_instance_id = uuid.UUID("00000000-0000-0000-0000-000000000101")
        self.failed_instance_id = uuid.UUID("00000000-0000-0000-0000-000000000102")
        self.frame = self._build_frame()
        self.instances = [
            SimpleNamespace(
                id=self.success_instance_id,
                name="P0 成功实例",
                status="online",
                collect_status="success",
            ),
            SimpleNamespace(
                id=self.failed_instance_id,
                name="P0 失败实例",
                status="collect_error",
                collect_status="failed",
            ),
        ]

    def _build_frame(self):
        snapshot_time = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
        frame = SimpleNamespace(
            frame_id=uuid.UUID("00000000-0000-0000-0000-000000000201"),
            instance_id=self.success_instance_id,
            snapshot_time=snapshot_time,
            collect_duration_ms=18,
            status="success",
        )

        sessions = [
            SimpleNamespace(
                session_id=11,
                login_name="app_blocker",
                host_name="web-01",
                program_name="P0 Blocker",
                database_name="P0DB",
                status="running",
                open_transaction_count=1,
                cpu_time=1_500,
                reads=2_000,
                writes=25,
                logical_reads=9_500,
                current_sql_hash="sql-blocker",
            ),
            SimpleNamespace(
                session_id=12,
                login_name="app_blocked",
                host_name="web-02",
                program_name="P0 Blocked",
                database_name="P0DB",
                status="suspended",
                open_transaction_count=1,
                cpu_time=800,
                reads=1_600,
                writes=15,
                logical_reads=4_200,
                current_sql_hash="sql-blocked",
            ),
            SimpleNamespace(
                session_id=13,
                login_name="app_idle",
                host_name="web-03",
                program_name="P0 Idle",
                database_name="P0DB",
                status="sleeping",
                open_transaction_count=0,
                cpu_time=120,
                reads=200,
                writes=2,
                logical_reads=500,
                current_sql_hash=None,
            ),
        ]

        requests = [
            SimpleNamespace(
                session_id=11,
                request_id=0,
                database_name="P0DB",
                status="running",
                command="UPDATE",
                start_time=snapshot_time,
                duration_ms=18_000,
                cpu_time_ms=1_400,
                total_elapsed_time_ms=18_000,
                reads=2_000,
                writes=25,
                logical_reads=9_500,
                row_count=1,
                sql_text="UPDATE dbo.Inventory SET Stock = Stock - 1 WHERE Id = 11",
                wait_type=None,
                wait_time_ms=None,
                blocking_session_id=None,
                resource_description=None,
                sql_hash="sql-blocker",
                normalized_sql_hash="sql-blocker-normalized",
                sql_preview="UPDATE dbo.Inventory SET Stock = Stock - 1 WHERE Id = 11",
            ),
            SimpleNamespace(
                session_id=12,
                request_id=0,
                database_name="P0DB",
                status="suspended",
                command="UPDATE",
                start_time=snapshot_time,
                duration_ms=24_000,
                cpu_time_ms=700,
                total_elapsed_time_ms=24_000,
                reads=1_600,
                writes=15,
                logical_reads=4_200,
                row_count=0,
                sql_text="UPDATE dbo.Inventory SET Reserved = Reserved + 1 WHERE Id = 11",
                wait_type="LCK_M_X",
                wait_time_ms=15_000,
                blocking_session_id=11,
                resource_description="KEY: 1:12345",
                sql_hash="sql-blocked",
                normalized_sql_hash="sql-blocked-normalized",
                sql_preview="UPDATE dbo.Inventory SET Reserved = Reserved + 1 WHERE Id = 11",
            ),
        ]

        waits = [
            SimpleNamespace(
                wait_type="LCK_M_X",
                wait_category="LOCK",
                waiting_tasks_count=1,
                total_wait_time_ms=15_000,
                max_wait_time_ms=15_000,
            )
        ]

        blocking_rows = [
            SimpleNamespace(
                root_session_id=11,
                blocking_session_id=11,
                blocked_session_id=12,
                chain_depth=1,
                blocked_count=1,
                max_wait_time_ms=15_000,
                wait_type="LCK_M_X",
                resource_description="KEY: 1:12345",
                cycle_detected=False,
                special_blocker_code=None,
            )
        ]

        frame.sessions = sessions
        frame.requests = requests
        frame.waits = waits
        frame.blocking_rows = blocking_rows
        return frame

    async def get_latest_frame(self, instance_id):
        if instance_id == self.success_instance_id:
            return self.frame
        return None

    async def get_frame_before(self, instance_id, target_time, max_delay_seconds):
        if instance_id != self.success_instance_id:
            return None
        if self.frame.snapshot_time > target_time:
            return None
        if (target_time - self.frame.snapshot_time).total_seconds() > max_delay_seconds:
            return None
        return self.frame

    async def list_sessions(self, frame):
        return list(self._frame_rows(frame, "sessions"))

    async def get_session(self, frame, session_id: int):
        return next((session for session in self._frame_rows(frame, "sessions") if session.session_id == session_id), None)

    async def list_requests(self, frame):
        return list(self._frame_rows(frame, "requests"))

    async def get_request_by_sql_hash(self, frame, sql_hash: str):
        return next(
            (request for request in self._frame_rows(frame, "requests") if request.sql_hash == sql_hash),
            None,
        )

    async def get_request_by_session(self, frame, session_id: int):
        return next(
            (request for request in self._frame_rows(frame, "requests") if request.session_id == session_id),
            None,
        )

    async def list_waits(self, frame):
        return list(self._frame_rows(frame, "waits"))

    async def list_blocking_rows(self, frame):
        return list(self._frame_rows(frame, "blocking_rows"))

    @staticmethod
    def _frame_rows(frame, attribute_name: str):
        value = getattr(frame, attribute_name, None)
        if value is not None:
            return value
        source = getattr(frame, "source", None)
        return getattr(source, attribute_name, [])


def _fake_user():
    return SimpleNamespace(id=uuid.uuid4(), username="p0-reviewer", role="viewer", status="active")


def _install_overrides(api_client, repository: FakeP0Repository):
    app = api_client.app
    app.dependency_overrides[get_db_session] = lambda: repository
    app.dependency_overrides[current_user] = _fake_user
    return app


def test_p0_seed_contains_success_and_failure_instances(api_client) -> None:
    repository = FakeP0Repository()
    app = _install_overrides(api_client, repository)

    assert len(repository.instances) == 2
    assert repository.instances[0].status == "online"
    assert repository.instances[1].status == "collect_error"

    app.dependency_overrides.clear()


def test_p0_dashboard_session_sql_blocking_and_replay_flow(api_client) -> None:
    repository = FakeP0Repository()
    app = _install_overrides(api_client, repository)

    dashboard_response = api_client.get(f"/api/dashboard?instance_id={repository.success_instance_id}")
    sessions_response = api_client.get(f"/api/sessions?instance_id={repository.success_instance_id}")
    sqls_response = api_client.get(f"/api/sqls?instance_id={repository.success_instance_id}")
    blocking_response = api_client.get(f"/api/blocking?instance_id={repository.success_instance_id}")
    replay_response = api_client.get(
        f"/api/replay?instance_id={repository.success_instance_id}&time=2026-05-10T12:00:02Z"
    )

    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert dashboard["metrics"]["session_count"] == 3
    assert dashboard["metrics"]["active_request_count"] == 2
    assert dashboard["metrics"]["blocked_session_count"] == 1
    assert dashboard["metrics"]["root_blocker_count"] == 1
    assert dashboard["metrics"]["waiting_request_count"] == 1

    assert sessions_response.status_code == 200
    sessions = sessions_response.json()
    assert sessions["total"] == 3
    assert len(sessions["items"]) == 3

    assert sqls_response.status_code == 200
    sqls = sqls_response.json()
    assert sqls["total"] == 2
    assert len(sqls["items"]) == 2

    assert blocking_response.status_code == 200
    blocking = blocking_response.json()
    assert len(blocking["chains"]) == 1
    assert blocking["chains"][0]["root_session_id"] == 11
    assert len(blocking["chains"][0]["nodes"]) == 1

    assert replay_response.status_code == 200
    replay = replay_response.json()
    assert replay["frame_id"] == str(repository.frame.frame_id)
    assert replay["snapshot_time"] == "2026-05-10T12:00:00Z"
    assert len(replay["sessions"]) == 3
    assert len(replay["sqls"]) == 2
    assert len(replay["blocking"]) == 1

    app.dependency_overrides.clear()


def test_p0_failed_instance_has_no_latest_frame(api_client) -> None:
    repository = FakeP0Repository()
    app = _install_overrides(api_client, repository)

    response = api_client.get(f"/api/dashboard?instance_id={repository.failed_instance_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "LATEST_FRAME_NOT_FOUND"

    app.dependency_overrides.clear()
