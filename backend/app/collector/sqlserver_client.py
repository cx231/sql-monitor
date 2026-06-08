from __future__ import annotations

from typing import Any, Optional, Sequence


class SqlServerClient:
    def __init__(
        self,
        connection_string: str,
        connect_timeout_seconds: int = 5,
        query_timeout_seconds: int = 10,
    ) -> None:
        self.connection_string = connection_string
        self.connect_timeout_seconds = connect_timeout_seconds
        self.query_timeout_seconds = query_timeout_seconds

    def query(
        self,
        sql: str,
        parameters: Optional[Sequence[Any]] = None,
        timeout_seconds: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        pyodbc = _load_pyodbc()
        connection = pyodbc.connect(
            self.connection_string,
            timeout=self.connect_timeout_seconds,
        )
        cursor = None
        try:
            cursor = connection.cursor()
            try:
                cursor.timeout = timeout_seconds or self.query_timeout_seconds
            except AttributeError:
                pass
            cursor.execute(sql, tuple(parameters or ()))
            columns = [column[0] for column in cursor.description or ()]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def execute(
        self,
        sql: str,
        parameters: Optional[Sequence[Any]] = None,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        pyodbc = _load_pyodbc()
        connection = pyodbc.connect(
            self.connection_string,
            timeout=self.connect_timeout_seconds,
        )
        cursor = None
        try:
            cursor = connection.cursor()
            try:
                cursor.timeout = timeout_seconds or self.query_timeout_seconds
            except AttributeError:
                pass
            cursor.execute(sql, tuple(parameters or ()))
            connection.commit()
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()


def _load_pyodbc() -> Any:
    try:
        import pyodbc
    except ImportError as exc:
        raise RuntimeError("pyodbc 未安装，无法连接 SQL Server") from exc

    return pyodbc
