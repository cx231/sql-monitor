from __future__ import annotations

import sys
from types import SimpleNamespace

from app.collector.collectors.resource_collector import RESOURCE_SQL
from app.collector.collectors.session_request_collector import SESSION_REQUEST_SQL
from app.collector.collectors.wait_collector import WAIT_SQL, categorize_wait
from app.collector.sqlserver_client import SqlServerClient


def test_session_request_sql_contains_required_dmvs() -> None:
    sql = SESSION_REQUEST_SQL.lower()

    assert "sys.dm_exec_sessions" in sql
    assert "sys.dm_exec_requests" in sql
    assert "sys.dm_exec_sql_text" in sql
    assert "is_user_process = 1" in sql


def test_wait_sql_contains_required_dmv() -> None:
    sql = WAIT_SQL.lower()

    assert "sys.dm_os_waiting_tasks" in sql
    assert "wait_duration_ms" in sql
    assert "resource_description" in sql


def test_resource_sql_reports_host_cpu_and_os_memory_usage() -> None:
    sql = RESOURCE_SQL.lower()
    cpu_case = sql.split("as cpu_load_percent", maxsplit=1)[0].rsplit("case", maxsplit=1)[1]

    assert "100 - cpu_sample.systemidle" in sql
    assert cpu_case.index("when cpu_sample.systemidle") < cpu_case.index(
        "when cpu_sample.sqlprocessutilization"
    )
    assert "sys.dm_os_sys_memory" in sql
    assert "total_physical_memory_kb" in sql
    assert "available_physical_memory_kb" in sql
    assert "sys.dm_os_process_memory" not in sql
    assert "memory_utilization_percentage" not in sql


def test_resource_sql_reports_network_send_and_receive_counters() -> None:
    sql = RESOURCE_SQL.lower()

    assert "network_bytes_sent_total" in sql
    assert "network_bytes_received_total" in sql
    assert "num_writes" in sql
    assert "num_reads" in sql


def test_categorize_wait_maps_p0_wait_categories() -> None:
    cases = {
        "LCK_M_X": "LOCK",
        "PAGEIOLATCH_SH": "IO",
        "WRITELOG": "LOG",
        "SOS_SCHEDULER_YIELD": "CPU",
        "CXPACKET": "PARALLELISM",
        "RESOURCE_SEMAPHORE": "MEMORY",
        "PAGELATCH_UP": "TEMPDB",
        "ASYNC_NETWORK_IO": "NETWORK",
        "UNKNOWN_WAIT": "OTHER",
        None: "OTHER",
    }

    for wait_type, expected_category in cases.items():
        assert categorize_wait(wait_type) == expected_category


def test_sqlserver_client_query_uses_timeout_and_returns_dict_rows(monkeypatch) -> None:
    executed = {}

    class FakeCursor:
        timeout = None
        description = (("session_id",), ("login_name",))

        def execute(self, sql: str, parameters: tuple[object, ...]) -> None:
            executed["sql"] = sql
            executed["parameters"] = parameters

        def fetchall(self) -> list[tuple[int, str]]:
            return [(51, "app_reader")]

        def close(self) -> None:
            executed["cursor_closed"] = True

    class FakeConnection:
        timeout = None

        def cursor(self) -> FakeCursor:
            cursor = FakeCursor()
            executed["cursor"] = cursor
            return cursor

        def close(self) -> None:
            executed["connection_closed"] = True

    def fake_connect(connection_string: str, timeout: int) -> FakeConnection:
        executed["connection_string"] = connection_string
        executed["connect_timeout"] = timeout
        return FakeConnection()

    monkeypatch.setitem(
        sys.modules,
        "pyodbc",
        SimpleNamespace(connect=fake_connect),
    )

    client = SqlServerClient(
        "Driver={ODBC Driver 18 for SQL Server};Server=db01;",
        connect_timeout_seconds=3,
        query_timeout_seconds=7,
    )

    rows = client.query("SELECT ? AS session_id", parameters=(51,))

    assert rows == [{"session_id": 51, "login_name": "app_reader"}]
    assert executed["connection_string"].startswith("Driver=")
    assert executed["connect_timeout"] == 3
    assert executed["cursor"].timeout == 7
    assert executed["parameters"] == (51,)
    assert executed["cursor_closed"] is True
    assert executed["connection_closed"] is True


def test_sqlserver_client_query_supports_cursors_without_timeout(monkeypatch) -> None:
    executed = {}

    class FakeCursor:
        __slots__ = ("description",)

        def __init__(self) -> None:
            self.description = (("database_name",),)

        def execute(self, sql: str, parameters: tuple[object, ...]) -> None:
            executed["sql"] = sql
            executed["parameters"] = parameters

        def fetchall(self) -> list[tuple[str]]:
            return [("master",)]

        def close(self) -> None:
            executed["cursor_closed"] = True

    class FakeConnection:
        def cursor(self) -> FakeCursor:
            return FakeCursor()

        def close(self) -> None:
            executed["connection_closed"] = True

    def fake_connect(connection_string: str, timeout: int) -> FakeConnection:
        executed["connection_string"] = connection_string
        executed["connect_timeout"] = timeout
        return FakeConnection()

    monkeypatch.setitem(
        sys.modules,
        "pyodbc",
        SimpleNamespace(connect=fake_connect),
    )

    client = SqlServerClient(
        "Driver={ODBC Driver 17 for SQL Server};Server=db01;",
        connect_timeout_seconds=3,
        query_timeout_seconds=7,
    )

    rows = client.query("SELECT DB_NAME() AS database_name")

    assert rows == [{"database_name": "master"}]
    assert executed["parameters"] == ()
    assert executed["cursor_closed"] is True
    assert executed["connection_closed"] is True
