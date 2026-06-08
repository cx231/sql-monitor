from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.collector.mock_data import build_mock_frame
from app.db.models import SnapshotFrame
from app.services.blocking_service import get_blocking_chains
from app.services.dashboard_service import SnapshotRepository
from app.services.dashboard_service import get_dashboard
from app.services.replay_service import get_replay_frame
from app.services.session_service import get_session_detail, list_sessions
from app.services.sql_service import get_sql_detail, list_sqls


class SeededSnapshotRepository:
    def __init__(self, frames):
        self.frames = sorted(frames, key=lambda frame: frame.snapshot_time)

    async def get_latest_frame(self, instance_id):
        candidates = [frame for frame in self.frames if frame.instance_id == instance_id]
        return candidates[-1] if candidates else None

    async def get_frame_before(self, instance_id, target_time, max_delay_seconds):
        candidates = [
            frame
            for frame in self.frames
            if frame.instance_id == instance_id
            and frame.snapshot_time <= target_time
            and (target_time - frame.snapshot_time).total_seconds() <= max_delay_seconds
        ]
        return candidates[-1] if candidates else None

    async def list_resource_frames(self, instance_id, since_time):
        return [
            frame
            for frame in self.frames
            if frame.instance_id == instance_id and frame.snapshot_time >= since_time
        ]

    async def get_resource_frame_before(self, instance_id, before_time):
        candidates = [
            frame
            for frame in self.frames
            if frame.instance_id == instance_id and frame.snapshot_time < before_time
        ]
        return candidates[-1] if candidates else None


def _with_blocking_row(frame, **overrides):
    base = {
        "root_session_id": 53,
        "blocking_session_id": 53,
        "blocked_session_id": 54,
        "chain_depth": 1,
        "blocked_count": 1,
        "max_wait_time_ms": 38_000,
        "wait_type": "LCK_M_X",
        "resource_description": "KEY: 7:72057594040549376 (ce52f92a058c)",
        "cycle_detected": False,
        "special_blocker_code": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _seeded_frame(instance_id, snapshot_time):
    frame = build_mock_frame(instance_id=instance_id, snapshot_time=snapshot_time)
    return SimpleNamespace(
        frame_id=frame.frame_id,
        instance_id=frame.instance_id,
        snapshot_time=frame.snapshot_time,
        collect_duration_ms=frame.collect_duration_ms,
        status=frame.status,
        cpu_load_percent=None,
        memory_usage_percent=None,
        network_bytes_sent_total=None,
        network_bytes_received_total=None,
        sessions=list(frame.sessions),
        requests=list(frame.requests),
        waits=list(frame.waits),
        blocking_rows=[
            _with_blocking_row(
                frame,
                root_session_id=edge.root_session_id,
                blocking_session_id=edge.blocker_session_id,
                blocked_session_id=edge.blocked_session_id,
                chain_depth=edge.chain_depth,
                blocked_count=1,
                max_wait_time_ms=edge.wait_duration_ms,
                wait_type=edge.wait_type,
                resource_description=edge.resource_description,
                cycle_detected=edge.cycle_detected,
            )
            for edge in frame.blocking_edges
        ],
    )


def test_dashboard_aggregates_latest_frame_counts_and_top_lists() -> None:
    instance_id = uuid.uuid4()
    frame = _seeded_frame(instance_id, datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc))
    repository = SeededSnapshotRepository([frame])

    result = asyncio.run(get_dashboard(repository, instance_id))

    assert result is not None
    assert result.instance_id == instance_id
    assert result.frame_id == frame.frame_id
    assert result.metrics.session_count == 4
    assert result.metrics.active_request_count == 2
    assert result.metrics.blocked_session_count == 1
    assert result.metrics.root_blocker_count == 1
    assert result.metrics.max_blocking_duration_ms == 38_000
    assert result.metrics.waiting_request_count == 1
    assert [wait.wait_type for wait in result.top_waits[:2]] == ["LCK_M_X", "PAGEIOLATCH_SH"]
    assert result.top_cpu_sqls[0].session_id == 52
    assert result.top_io_sqls[0].session_id == 52


def test_dashboard_returns_resource_trends_for_selected_window() -> None:
    instance_id = uuid.uuid4()
    base_time = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
    old_frame = _seeded_frame(instance_id, base_time - timedelta(minutes=10))
    first_frame = _seeded_frame(instance_id, base_time - timedelta(minutes=4))
    latest_frame = _seeded_frame(instance_id, base_time)
    old_frame.network_bytes_sent_total = 100_000
    old_frame.network_bytes_received_total = 200_000
    first_frame.cpu_load_percent = 18.5
    first_frame.memory_usage_percent = 62.0
    first_frame.network_bytes_sent_total = 700_000
    first_frame.network_bytes_received_total = 1_400_000
    latest_frame.cpu_load_percent = 24.0
    latest_frame.memory_usage_percent = 65.5
    latest_frame.network_bytes_sent_total = 1_000_000
    latest_frame.network_bytes_received_total = 2_000_000
    repository = SeededSnapshotRepository([old_frame, first_frame, latest_frame])

    result = asyncio.run(get_dashboard(repository, instance_id, metrics_window_minutes=5))

    assert result is not None
    assert result.metrics_window_minutes == 5
    assert [point.snapshot_time for point in result.resource_trends] == [
        first_frame.snapshot_time,
        latest_frame.snapshot_time,
    ]
    assert result.resource_trends[0].network_send_rate_bytes_per_sec == 1_666.6666666666667
    assert result.resource_trends[0].network_receive_rate_bytes_per_sec == 3_333.3333333333335
    assert result.resource_trends[1].cpu_load_percent == 24.0
    assert result.resource_trends[1].memory_usage_percent == 65.5
    assert result.resource_trends[1].network_send_rate_bytes_per_sec == 1_250.0
    assert result.resource_trends[1].network_receive_rate_bytes_per_sec == 2_500.0


def test_dashboard_treats_network_counter_reset_as_zero_rate() -> None:
    instance_id = uuid.uuid4()
    base_time = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
    previous_frame = _seeded_frame(instance_id, base_time - timedelta(minutes=1))
    latest_frame = _seeded_frame(instance_id, base_time)
    previous_frame.network_bytes_sent_total = 1_000_000
    previous_frame.network_bytes_received_total = 2_000_000
    latest_frame.network_bytes_sent_total = 900_000
    latest_frame.network_bytes_received_total = 1_900_000
    repository = SeededSnapshotRepository([previous_frame, latest_frame])

    result = asyncio.run(get_dashboard(repository, instance_id, metrics_window_minutes=5))

    assert result is not None
    assert result.resource_trends[1].network_send_rate_bytes_per_sec == 0.0
    assert result.resource_trends[1].network_receive_rate_bytes_per_sec == 0.0


def test_session_list_filters_blocked_open_transactions_and_paginates() -> None:
    instance_id = uuid.uuid4()
    frame = _seeded_frame(instance_id, datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc))
    repository = SeededSnapshotRepository([frame])

    result = asyncio.run(
        list_sessions(
            repository,
            instance_id,
            status="suspended",
            only_blocked=True,
            only_open_transaction=True,
            page=1,
            page_size=1,
        )
    )

    assert result.total == 1
    assert len(result.items) == 1
    item = result.items[0]
    assert item.session_id == 54
    assert item.status == "suspended"
    assert item.open_transaction_count == 1
    assert item.blocking_session_id == 53
    assert item.current_sql_preview is not None


def test_realtime_list_outputs_include_backend_collect_delay() -> None:
    instance_id = uuid.uuid4()
    frame = _seeded_frame(instance_id, datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc))
    repository = SeededSnapshotRepository([frame])

    sessions = asyncio.run(list_sessions(repository, instance_id))
    sqls = asyncio.run(list_sqls(repository, instance_id))
    blocking = asyncio.run(get_blocking_chains(repository, instance_id))

    assert sessions is not None
    assert sqls is not None
    assert blocking is not None
    assert sessions.collect_delay_seconds >= 0
    assert sqls.collect_delay_seconds >= 0
    assert blocking.collect_delay_seconds >= 0


def test_sql_list_sorts_by_wait_time_desc_and_pages() -> None:
    instance_id = uuid.uuid4()
    frame = _seeded_frame(instance_id, datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc))
    repository = SeededSnapshotRepository([frame])

    result = asyncio.run(
        list_sqls(
            repository,
            instance_id,
            page=1,
            page_size=1,
            sort_by="wait_time_ms",
            sort_order="desc",
        )
    )

    assert result.total == 2
    assert len(result.items) == 1
    assert result.items[0].session_id == 54
    assert result.items[0].wait_time_ms == 38_000
    assert result.items[0].sql_preview is not None


def test_session_detail_uses_repository_detail_lookup_when_list_is_bounded_elsewhere() -> None:
    instance_id = uuid.uuid4()
    frame = _seeded_frame(instance_id, datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc))

    class DetailRepository(SeededSnapshotRepository):
        async def list_sessions(self, frame):
            return []

        async def get_session(self, frame, session_id):
            return next(item for item in self.frames[0].sessions if item.session_id == session_id)

        async def list_requests(self, frame):
            return []

        async def get_request_by_session(self, frame, session_id):
            return next(item for item in self.frames[0].requests if item.session_id == session_id)

    result = asyncio.run(get_session_detail(DetailRepository([frame]), instance_id, 54))

    assert result is not None
    assert result.session_id == 54
    assert result.blocking_session_id == 53
    assert result.current_sql_preview is not None


def test_sql_detail_uses_repository_detail_lookup_when_list_is_bounded_elsewhere() -> None:
    instance_id = uuid.uuid4()
    frame = _seeded_frame(instance_id, datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc))
    request = frame.requests[0]

    class DetailRepository(SeededSnapshotRepository):
        async def list_requests(self, frame):
            return []

        async def get_request_by_sql_hash(self, frame, sql_hash):
            return next(item for item in self.frames[0].requests if item.sql_hash == sql_hash)

    result = asyncio.run(get_sql_detail(DetailRepository([frame]), instance_id, request.sql_hash))

    assert result is not None
    assert result.sql_hash == request.sql_hash
    assert result.sql_preview is not None
    assert result.sql_text == request.sql_text


def test_blocking_chains_group_by_root_and_sort_by_impact_then_wait() -> None:
    instance_id = uuid.uuid4()
    frame = _seeded_frame(instance_id, datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc))
    frame.blocking_rows.append(
        _with_blocking_row(
            frame,
            root_session_id=60,
            blocking_session_id=60,
            blocked_session_id=61,
            blocked_count=3,
            max_wait_time_ms=10_000,
        )
    )
    frame.blocking_rows.append(
        _with_blocking_row(
            frame,
            root_session_id=70,
            blocking_session_id=70,
            blocked_session_id=71,
            blocked_count=3,
            max_wait_time_ms=20_000,
        )
    )
    repository = SeededSnapshotRepository([frame])

    result = asyncio.run(get_blocking_chains(repository, instance_id))

    assert result is not None
    assert [chain.root_session_id for chain in result.chains] == [70, 60, 53]
    assert result.chains[0].blocked_count == 3
    assert result.chains[0].max_wait_time_ms == 20_000
    assert result.chains[0].risk_level == "medium"


def test_replay_uses_latest_frame_before_target_with_default_tolerance() -> None:
    instance_id = uuid.uuid4()
    target_time = datetime(2026, 5, 10, 12, 0, 10, tzinfo=timezone.utc)
    older_frame = _seeded_frame(instance_id, target_time - timedelta(seconds=20))
    selected_frame = _seeded_frame(instance_id, target_time - timedelta(seconds=2))
    future_frame = _seeded_frame(instance_id, target_time + timedelta(seconds=1))
    repository = SeededSnapshotRepository([older_frame, selected_frame, future_frame])

    result = asyncio.run(get_replay_frame(repository, instance_id, target_time))

    assert result is not None
    assert result.requested_time == target_time
    assert result.frame_id == selected_frame.frame_id
    assert result.snapshot_time == selected_frame.snapshot_time
    assert result.dashboard.metrics.session_count == 4
    assert len(result.sessions) == 4
    assert len(result.sqls) == 2
    assert len(result.blocking) == 1
    assert len(result.waits) == 3


def test_replay_returns_none_when_nearest_prior_frame_exceeds_tolerance() -> None:
    instance_id = uuid.uuid4()
    target_time = datetime(2026, 5, 10, 12, 0, 10, tzinfo=timezone.utc)
    frame = _seeded_frame(instance_id, target_time - timedelta(seconds=11))
    repository = SeededSnapshotRepository([frame])

    result = asyncio.run(get_replay_frame(repository, instance_id, target_time))

    assert result is None


def test_snapshot_repository_accepts_snapshot_frame_orm_without_frame_id_attribute() -> None:
    frame = SnapshotFrame(
        id=uuid.uuid4(),
        instance_id=uuid.uuid4(),
        snapshot_time=datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc),
        collect_duration_ms=12,
        status="success",
    )

    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return []

    class FakeSession:
        def __init__(self):
            self.executed = []

        async def execute(self, statement):
            self.executed.append(statement)
            return FakeResult()

    fake_session = FakeSession()
    repository = SnapshotRepository(fake_session)

    assert not hasattr(frame, "frame_id")
    result = asyncio.run(repository.list_sessions(frame))

    assert result == []
    assert len(fake_session.executed) == 1
