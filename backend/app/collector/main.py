from __future__ import annotations

import argparse
import asyncio
import time
import uuid
from typing import Optional

from app.collector.instance_runner import collect_instance_once
from app.collector.real_instance_collector import (
    collect_instance_snapshot,
    list_collectable_instances,
    collect_index_snapshots_for_instance,
)
from app.db.postgres import async_session_factory

_index_collection_tasks: dict[uuid.UUID, asyncio.Task] = {}


def run_collector(
    instance_id: Optional[uuid.UUID] = None,
    interval_seconds: int = 5,
    run_once: bool = False,
    use_mock: bool = False,
) -> None:
    """启动 Collector 主循环。"""

    if use_mock:
        run_mock_collector(instance_id, interval_seconds, run_once)
        return

    asyncio.run(run_real_collector(instance_id, interval_seconds, run_once))


async def run_real_collector(
    instance_id: Optional[uuid.UUID] = None,
    interval_seconds: int = 5,
    run_once: bool = False,
) -> None:
    while True:
        await collect_instances_once(instance_id)

        if run_once:
            return

        await asyncio.sleep(interval_seconds)


def run_mock_collector(
    instance_id: Optional[uuid.UUID] = None,
    interval_seconds: int = 5,
    run_once: bool = False,
) -> None:
    while True:
        frame = collect_instance_once(instance_id)
        print(
            "collector mock frame "
            f"instance_id={frame.instance_id} "
            f"snapshot_time={frame.snapshot_time.isoformat()} "
            f"sessions={len(frame.sessions)} "
            f"requests={len(frame.requests)} "
            f"blocking_edges={len(frame.blocking_edges)}",
            flush=True,
        )

        if run_once:
            return

        time.sleep(interval_seconds)


async def collect_instances_once(instance_id: Optional[uuid.UUID] = None) -> None:
    async with async_session_factory() as session:
        pairs = await list_collectable_instances(session)
        if instance_id is not None:
            pairs = [
                (instance, collect_status)
                for instance, collect_status in pairs
                if instance.id == instance_id
            ]

        if not pairs:
            print("collector no collectable instances", flush=True)
            return

        for instance, collect_status in pairs:
            result = await collect_instance_snapshot(
                session,
                instance,
                collect_status=collect_status,
                collect_indexes=False,
            )
            if result.success:
                print(
                    "collector frame "
                    f"instance_id={result.instance_id} "
                    f"frame_id={result.frame_id} "
                    f"sessions={result.sessions_collected} "
                    f"requests={result.requests_collected} "
                    f"waits={result.waits_collected} "
                    f"blocking_edges={result.blocking_edges_collected}",
                    flush=True,
                )
                schedule_index_collection_for_instance(result.instance_id)
            else:
                print(
                    "collector failed "
                    f"instance_id={result.instance_id} "
                    f"error={result.error_message}",
                    flush=True,
                )


def schedule_index_collection_for_instance(instance_id: uuid.UUID) -> bool:
    task = _index_collection_tasks.get(instance_id)
    if task is not None and not task.done():
        return False

    task = asyncio.create_task(_run_index_collection_for_instance(instance_id))
    _index_collection_tasks[instance_id] = task
    task.add_done_callback(lambda done_task: _finish_index_collection_task(instance_id, done_task))
    return True


def _finish_index_collection_task(instance_id: uuid.UUID, task: asyncio.Task) -> None:
    if _index_collection_tasks.get(instance_id) is task:
        _index_collection_tasks.pop(instance_id, None)
    try:
        task.result()
    except Exception as exc:
        print(
            "collector index background failed "
            f"instance_id={instance_id} "
            f"error={exc}",
            flush=True,
        )


async def _run_index_collection_for_instance(instance_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        await collect_index_snapshots_for_instance(session, instance_id)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SQLMon Collector 入口")
    parser.add_argument("--instance-id", type=uuid.UUID, default=None, help="实例 UUID")
    parser.add_argument("--interval-seconds", type=int, default=5, help="采集间隔秒数")
    parser.add_argument("--once", action="store_true", help="只采集一次后退出")
    parser.add_argument("--mock", action="store_true", help="使用 mock 采集帧")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    run_collector(
        instance_id=args.instance_id,
        interval_seconds=args.interval_seconds,
        run_once=args.once,
        use_mock=args.mock,
    )


if __name__ == "__main__":
    main()
