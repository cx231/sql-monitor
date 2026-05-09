from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from app.services.kill_service import (
    KillExecutor,
    KillRejectedError,
    KillTarget,
    kill_session,
    validate_kill_target,
)


class RecordingExecutor(KillExecutor):
    def __init__(self, should_fail: bool = False, failure_message: str = "executor failed"):
        self.should_fail = should_fail
        self.failure_message = failure_message
        self.calls: list[tuple[uuid.UUID, int]] = []

    async def kill(self, instance_id: uuid.UUID, session_id: int) -> None:
        self.calls.append((instance_id, session_id))
        if self.should_fail:
            raise RuntimeError(self.failure_message)


class RecordingAuditStore:
    def __init__(self):
        self.records: list[dict[str, object]] = []
        self.frame = None
        self.instance_exists = False

    async def write_kill_audit(self, **kwargs):
        self.records.append(kwargs)
        return SimpleNamespace(id=uuid.uuid4(), **kwargs)

    async def has_instance(self, instance_id):
        return self.instance_exists

    async def get_latest_frame(self, instance_id):
        return self.frame


def _target(**overrides) -> KillTarget:
    values = {
        "instance_id": uuid.uuid4(),
        "session_id": 72,
        "login_name": "business_user",
        "status": "running",
        "open_transaction_count": 1,
        "blocking_impact_count": 3,
        "host_name": "app01",
        "program_name": "orders-api",
        "database_name": "orders",
        "current_sql_hash": "abc123",
        "current_sql_preview": "UPDATE orders SET status = ?",
        "wait_type": "LCK_M_X",
        "wait_time_ms": 38000,
        "cpu_time": 120,
        "reads": 10,
        "writes": 5,
        "logical_reads": 900,
    }
    values.update(overrides)
    return KillTarget(**values)


def _operator(role: str = "dba"):
    return SimpleNamespace(id=uuid.uuid4(), username="alice", role=role)


def test_validate_kill_target_rejects_short_reason() -> None:
    with pytest.raises(KillRejectedError) as exc_info:
        validate_kill_target(_target(), reason="太短")

    assert exc_info.value.code == "REASON_TOO_SHORT"


@pytest.mark.parametrize("session_id", [1, 50])
def test_validate_kill_target_rejects_system_session(session_id: int) -> None:
    with pytest.raises(KillRejectedError) as exc_info:
        validate_kill_target(_target(session_id=session_id), reason="业务阻塞超过十分钟需要释放")

    assert exc_info.value.code == "SYSTEM_SESSION"


@pytest.mark.parametrize("login_name", ["sqlmon_collect", "sqlmon_kill"])
def test_validate_kill_target_rejects_platform_accounts(login_name: str) -> None:
    with pytest.raises(KillRejectedError) as exc_info:
        validate_kill_target(_target(login_name=login_name), reason="业务阻塞超过十分钟需要释放")

    assert exc_info.value.code == "PLATFORM_ACCOUNT"


@pytest.mark.parametrize("status", ["KILLED", "ROLLBACK", "killed/rollback"])
def test_validate_kill_target_rejects_terminal_status(status: str) -> None:
    with pytest.raises(KillRejectedError) as exc_info:
        validate_kill_target(_target(status=status), reason="业务阻塞超过十分钟需要释放")

    assert exc_info.value.code == "SESSION_TERMINATING"


def test_kill_session_executes_and_writes_success_audit() -> None:
    target = _target()
    executor = RecordingExecutor()
    audits = RecordingAuditStore()

    response = asyncio.run(
        kill_session(
            target=target,
            reason="业务阻塞超过十分钟，需要释放链路",
            operator=_operator(),
            executor=executor,
            audit_store=audits,
        )
    )

    assert response.result == "success"
    assert executor.calls == [(target.instance_id, target.session_id)]
    assert audits.records[0]["result"] == "success"
    assert audits.records[0]["before_snapshot"] == {
        "session_id": 72,
        "login_name": "business_user",
        "status": "running",
        "open_transaction_count": 1,
        "blocking_impact_count": 3,
        "host_name": "app01",
        "program_name": "orders-api",
        "database_name": "orders",
        "current_sql_hash": "abc123",
        "current_sql_preview": "UPDATE orders SET status = ?",
        "wait_type": "LCK_M_X",
        "wait_time_ms": 38000,
        "cpu_time": 120,
        "reads": 10,
        "writes": 5,
        "logical_reads": 900,
    }


def test_kill_session_rejected_target_writes_audit_without_executing() -> None:
    target = _target(login_name="sqlmon_collect")
    executor = RecordingExecutor()
    audits = RecordingAuditStore()

    response = asyncio.run(
        kill_session(
            target=target,
            reason="业务阻塞超过十分钟，需要释放链路",
            operator=_operator(),
            executor=executor,
            audit_store=audits,
        )
    )

    assert response.result == "rejected"
    assert response.error_message == "PLATFORM_ACCOUNT"
    assert executor.calls == []
    assert audits.records[0]["result"] == "rejected"


def test_kill_session_executor_failure_writes_failed_audit() -> None:
    target = _target()
    executor = RecordingExecutor(should_fail=True)
    audits = RecordingAuditStore()

    response = asyncio.run(
        kill_session(
            target=target,
            reason="业务阻塞超过十分钟，需要释放链路",
            operator=_operator(),
            executor=executor,
            audit_store=audits,
        )
    )

    assert response.result == "failed"
    assert response.error_message == "KILL_EXECUTION_FAILED"
    assert audits.records[0]["result"] == "failed"
    assert audits.records[0]["error_message"] == "KILL_EXECUTION_FAILED"


def test_kill_session_executor_failure_redacts_sensitive_exception() -> None:
    target = _target()
    sensitive_message = (
        "connect failed for DSN=sqlserver://sa:password=Secret123@example;pwd=Secret123"
    )
    executor = RecordingExecutor(should_fail=True, failure_message=sensitive_message)
    audits = RecordingAuditStore()

    response = asyncio.run(
        kill_session(
            target=target,
            reason="业务阻塞超过十分钟，需要释放链路",
            operator=_operator(),
            executor=executor,
            audit_store=audits,
        )
    )

    assert response.result == "failed"
    assert response.error_message == "KILL_EXECUTION_FAILED"
    assert sensitive_message not in response.model_dump_json()
    assert sensitive_message not in str(audits.records)
    assert "Secret123" not in response.model_dump_json()
    assert "Secret123" not in str(audits.records)


def test_kill_and_audit_routes_require_dba_or_admin(api_client) -> None:
    viewer = SimpleNamespace(id=uuid.uuid4(), username="bob", role="viewer", status="active")
    app = api_client.app

    from app.api.deps import current_user, get_db_session

    app.dependency_overrides[current_user] = lambda: viewer
    app.dependency_overrides[get_db_session] = lambda: RecordingAuditStore()

    instance_id = uuid.uuid4()
    kill_response = api_client.post(
        "/api/kill",
        json={
            "instance_id": str(instance_id),
            "session_id": 72,
            "reason": "业务阻塞超过十分钟，需要释放链路",
        },
    )
    audit_response = api_client.get("/api/audits/kills")

    assert kill_response.status_code == 403
    assert audit_response.status_code == 403
    app.dependency_overrides.clear()


def test_kill_route_returns_instance_not_found_without_audit(api_client) -> None:
    dba = SimpleNamespace(id=uuid.uuid4(), username="alice", role="dba", status="active")
    app = api_client.app
    store = RecordingAuditStore()

    from app.api.deps import current_user, get_db_session

    app.dependency_overrides[current_user] = lambda: dba
    app.dependency_overrides[get_db_session] = lambda: store

    response = api_client.post(
        "/api/kill",
        json={
            "instance_id": str(uuid.uuid4()),
            "session_id": 72,
            "reason": "业务阻塞超过十分钟，需要释放链路",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "INSTANCE_NOT_FOUND"
    assert store.records == []
    app.dependency_overrides.clear()


def test_kill_route_rejects_missing_session_for_existing_instance(api_client) -> None:
    dba = SimpleNamespace(id=uuid.uuid4(), username="alice", role="dba", status="active")
    app = api_client.app
    store = RecordingAuditStore()
    store.instance_exists = True
    store.frame = SimpleNamespace(
        frame_id=uuid.uuid4(),
        instance_id=uuid.uuid4(),
        snapshot_time=None,
    )

    from app.api.deps import current_user, get_db_session

    app.dependency_overrides[current_user] = lambda: dba
    app.dependency_overrides[get_db_session] = lambda: store

    response = api_client.post(
        "/api/kill",
        json={
            "instance_id": str(store.frame.instance_id),
            "session_id": 72,
            "reason": "业务阻塞超过十分钟，需要释放链路",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "SESSION_NOT_FOUND"
    assert store.records[0]["result"] == "rejected"
    assert store.records[0]["before_snapshot"]["session_id"] == 72
    assert store.records[0]["before_snapshot"]["blocking_impact_count"] == 0
    app.dependency_overrides.clear()
