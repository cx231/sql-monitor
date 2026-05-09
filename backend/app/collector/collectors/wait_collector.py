from __future__ import annotations

from typing import Optional

WAIT_SQL = """
SELECT
    wt.session_id,
    wt.exec_context_id,
    wt.wait_duration_ms,
    wt.wait_type,
    wt.blocking_session_id,
    wt.resource_description
FROM sys.dm_os_waiting_tasks wt
WHERE wt.session_id IS NOT NULL;
""".strip()


def categorize_wait(wait_type: Optional[str]) -> str:
    if not wait_type:
        return "OTHER"

    normalized_wait_type = wait_type.upper()

    if normalized_wait_type.startswith("LCK_"):
        return "LOCK"
    if normalized_wait_type.startswith(("PAGEIOLATCH_", "IO_COMPLETION", "ASYNC_IO_COMPLETION")):
        return "IO"
    if normalized_wait_type in {"WRITELOG", "LOGBUFFER"} or normalized_wait_type.startswith("LOG_RATE_"):
        return "LOG"
    if normalized_wait_type in {"SOS_SCHEDULER_YIELD", "THREADPOOL"}:
        return "CPU"
    if normalized_wait_type.startswith(("CXPACKET", "CXCONSUMER", "EXCHANGE")):
        return "PARALLELISM"
    if normalized_wait_type.startswith("RESOURCE_SEMAPHORE") or normalized_wait_type in {
        "MEMORY_ALLOCATION_EXT",
        "CMEMTHREAD",
    }:
        return "MEMORY"
    if normalized_wait_type.startswith("PAGELATCH_"):
        return "TEMPDB"
    if normalized_wait_type in {"ASYNC_NETWORK_IO", "NET_WAITFOR_PACKET"}:
        return "NETWORK"

    return "OTHER"
