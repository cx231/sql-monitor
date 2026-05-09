from __future__ import annotations

import argparse
import time
import uuid
from typing import Optional

from app.collector.instance_runner import collect_instance_once


def run_collector(
    instance_id: Optional[uuid.UUID] = None,
    interval_seconds: int = 5,
    run_once: bool = False,
) -> None:
    """启动 Collector 主循环；当前阶段仅生成 mock 快照，不连接真实 SQL Server。"""

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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SQLMon Collector mock 入口")
    parser.add_argument("--instance-id", type=uuid.UUID, default=None, help="实例 UUID")
    parser.add_argument("--interval-seconds", type=int, default=5, help="采集间隔秒数")
    parser.add_argument("--once", action="store_true", help="只采集一次后退出")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    run_collector(
        instance_id=args.instance_id,
        interval_seconds=args.interval_seconds,
        run_once=args.once,
    )


if __name__ == "__main__":
    main()
