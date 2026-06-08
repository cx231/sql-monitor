from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.collector import main as collector_main
from app.db.models import Instance, InstanceCollectStatus
from app.services.instance_service import encrypt_connection_string


def test_real_collector_reuses_one_event_loop_across_polling_cycles(monkeypatch) -> None:
    loops: list[asyncio.AbstractEventLoop] = []

    class StopCollector(Exception):
        pass

    async def fake_collect_instances_once(instance_id=None) -> None:
        loops.append(asyncio.get_running_loop())
        if len(loops) == 2:
            raise StopCollector

    monkeypatch.setattr(collector_main, "collect_instances_once", fake_collect_instances_once)
    monkeypatch.setattr(collector_main.time, "sleep", lambda seconds: None)

    with pytest.raises(StopCollector):
        collector_main.run_collector(interval_seconds=0)

    assert len(loops) == 2
    assert loops[0] is loops[1]


def test_collect_instances_once_reloads_instance_intervals_each_cycle(monkeypatch) -> None:
    instance_id = uuid.uuid4()
    observed_missing_intervals: list[int] = []
    observed_fragmentation_intervals: list[int] = []
    cycle = 0

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    def make_instance(missing_interval: int, fragmentation_interval: int) -> Instance:
        return Instance(
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
            missing_index_collect_interval_seconds=missing_interval,
            index_fragmentation_collect_interval_seconds=fragmentation_interval,
            created_at=datetime(2026, 5, 14, 9, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 5, 14, 9, 0, tzinfo=timezone.utc),
        )

    async def fake_list_collectable_instances(session):
        nonlocal cycle
        cycle += 1
        if cycle == 1:
            instance = make_instance(600, 900)
        else:
            instance = make_instance(120, 300)
        return [(instance, InstanceCollectStatus(instance_id=instance_id, status="success"))]

    scheduled_index_collections: list[uuid.UUID] = []

    async def fake_collect_instance_snapshot(session, instance, *, collect_status=None, collect_indexes=True):
        assert collect_indexes is False
        observed_missing_intervals.append(instance.missing_index_collect_interval_seconds)
        observed_fragmentation_intervals.append(instance.index_fragmentation_collect_interval_seconds)
        return SimpleNamespace(
            success=True,
            instance_id=instance.id,
            frame_id=uuid.uuid4(),
            sessions_collected=0,
            requests_collected=0,
            waits_collected=0,
            blocking_edges_collected=0,
        )

    def fake_schedule_index_collection(instance_id):
        scheduled_index_collections.append(instance_id)
        return True

    monkeypatch.setattr(collector_main, "async_session_factory", lambda: FakeSession())
    monkeypatch.setattr(collector_main, "list_collectable_instances", fake_list_collectable_instances)
    monkeypatch.setattr(collector_main, "collect_instance_snapshot", fake_collect_instance_snapshot)
    monkeypatch.setattr(collector_main, "schedule_index_collection_for_instance", fake_schedule_index_collection)

    asyncio.run(collector_main.collect_instances_once(instance_id))
    asyncio.run(collector_main.collect_instances_once(instance_id))

    assert observed_missing_intervals == [600, 120]
    assert observed_fragmentation_intervals == [900, 300]
    assert scheduled_index_collections == [instance_id, instance_id]
