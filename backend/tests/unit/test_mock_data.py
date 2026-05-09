from __future__ import annotations

import uuid

from app.collector.mock_data import build_mock_frame


def test_build_mock_frame_contains_blocked_request() -> None:
    instance_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

    frame = build_mock_frame(instance_id=instance_id)

    assert frame.instance_id == instance_id
    assert len(frame.sessions) >= 3
    assert len(frame.requests) >= 2

    blocked_requests = [
        request for request in frame.requests if request.blocking_session_id is not None
    ]
    assert blocked_requests

    blocked_request = blocked_requests[0]
    assert blocked_request.session_id == 54
    assert blocked_request.blocking_session_id == 53
    assert blocked_request.wait_type == "LCK_M_X"
    assert blocked_request.wait_time_ms > 0
    assert blocked_request.sql_hash
    assert blocked_request.normalized_sql_hash

    assert any(edge.root_session_id == 53 for edge in frame.blocking_edges)
    assert any(edge.blocked_session_id == 54 for edge in frame.blocking_edges)
    assert any(wait.wait_category == "LOCK" for wait in frame.waits)


def test_build_mock_frame_includes_high_cpu_and_high_io_examples() -> None:
    frame = build_mock_frame()

    high_cpu = max(frame.requests, key=lambda request: request.cpu_time_ms or 0)
    high_io_session = max(frame.sessions, key=lambda session: session.logical_reads or 0)

    assert high_cpu.session_id == 52
    assert high_cpu.cpu_time_ms >= 300_000
    assert high_io_session.session_id == 51
    assert high_io_session.logical_reads >= 20_000_000
