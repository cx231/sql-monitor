from __future__ import annotations

import base64
import re
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collector.sqlserver_client import SqlServerClient
from app.db.models import Instance, InstanceCollectStatus
from app.schemas.instances import (
    InstanceConnectionTestOut,
    InstanceConnectionTestRequest,
    InstanceCreate,
    InstanceOut,
    InstanceUpdate,
)

CONNECTION_TEST_SQL = """
SELECT
  CONCAT(
    'SQL Server ',
    CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(64)),
    ' ',
    COALESCE(CAST(SERVERPROPERTY('ProductLevel') AS nvarchar(64)), ''),
    ' ',
    CAST(SERVERPROPERTY('Edition') AS nvarchar(128))
  ) AS sqlserver_version,
  DB_NAME() AS database_name,
  CAST(NULL AS sysname) AS available_database_name
UNION ALL
SELECT
  CAST(NULL AS nvarchar(max)) AS sqlserver_version,
  CAST(NULL AS sysname) AS database_name,
  name AS available_database_name
FROM sys.databases
WHERE state_desc = 'ONLINE'
ORDER BY available_database_name
"""
DEFAULT_SQL_SERVER_ODBC_DRIVER = "ODBC Driver 18 for SQL Server"


def encrypt_connection_string(connection_string: str) -> str:
    # P0 占位实现：仅用于接口打通，后续需替换为真实加密/KMS。
    return base64.b64encode(connection_string.encode("utf-8")).decode("ascii")


def decrypt_connection_string(encrypted_connection_string: str) -> str:
    # P0 占位实现：仅用于接口打通，后续需替换为真实解密/KMS。
    return base64.b64decode(encrypted_connection_string.encode("ascii")).decode("utf-8")


def _odbc_brace(value: object) -> str:
    return "{" + str(value).replace("}", "}}") + "}"


def _resolve_sql_server_odbc_driver() -> str:
    try:
        import pyodbc
    except ImportError:
        return DEFAULT_SQL_SERVER_ODBC_DRIVER

    candidates = []
    for driver_name in pyodbc.drivers():
        match = re.fullmatch(r"ODBC Driver (\d+) for SQL Server", driver_name)
        if match:
            candidates.append((int(match.group(1)), driver_name))

    if not candidates:
        return DEFAULT_SQL_SERVER_ODBC_DRIVER

    return max(candidates, key=lambda candidate: candidate[0])[1]


def build_sql_auth_connection_string(
    host: str,
    port: int,
    username: str,
    password: str,
    database_name: str = "master",
) -> str:
    parts = [
        f"Driver={_odbc_brace(_resolve_sql_server_odbc_driver())}",
        f"Server={_odbc_brace(f'{host},{port}')}",
        f"Database={_odbc_brace(database_name or 'master')}",
        f"UID={_odbc_brace(username)}",
        f"PWD={_odbc_brace(password)}",
        "Encrypt=yes",
        "TrustServerCertificate=yes",
    ]
    return ";".join(parts) + ";"


def _run_connection_test(
    connection_string: str,
    client_factory: Callable[[str], Any] = SqlServerClient,
) -> InstanceConnectionTestOut:
    try:
        rows = client_factory(connection_string).query(CONNECTION_TEST_SQL, timeout_seconds=5)
    except Exception:
        return InstanceConnectionTestOut(
            success=False,
            error_message="连接测试失败",
        )

    sqlserver_version = None
    database_name = None
    databases: list[str] = []

    for row in rows:
        if sqlserver_version is None and row.get("sqlserver_version"):
            sqlserver_version = row.get("sqlserver_version")
        if database_name is None and row.get("database_name"):
            database_name = row.get("database_name")

        available_database_name = row.get("available_database_name")
        if available_database_name and available_database_name not in databases:
            databases.append(available_database_name)

    if not databases:
        databases = [database_name or "master"]

    return InstanceConnectionTestOut(
        success=True,
        sqlserver_version=sqlserver_version,
        database_name=database_name,
        databases=databases,
    )


def test_new_instance_connection(
    data: InstanceConnectionTestRequest,
    client_factory: Callable[[str], Any] = SqlServerClient,
) -> InstanceConnectionTestOut:
    connection_string = build_sql_auth_connection_string(
        host=data.host,
        port=data.port,
        username=data.username,
        password=data.password,
        database_name=data.database_name or "master",
    )
    return _run_connection_test(connection_string, client_factory)


async def test_existing_instance_connection(
    session: AsyncSession,
    instance_id: uuid.UUID,
    client_factory: Callable[[str], Any] = SqlServerClient,
) -> InstanceConnectionTestOut | None:
    instance = await session.get(Instance, instance_id)
    if instance is None:
        return None

    connection_string = decrypt_connection_string(instance.encrypted_collect_dsn)
    result = _run_connection_test(connection_string, client_factory)
    if not result.success:
        instance.status = "offline"
        await session.commit()
        await session.refresh(instance)
        result.instance = _to_instance_out(instance)
        return result

    instance.status = "online"
    if result.sqlserver_version:
        instance.sqlserver_version = result.sqlserver_version
    if result.database_name:
        instance.database_name = result.database_name

    await session.commit()
    await session.refresh(instance)
    result.instance = _to_instance_out(instance)
    return result


def _to_instance_out(instance: Instance) -> InstanceOut:
    return InstanceOut(
        id=instance.id,
        name=instance.name,
        host=instance.host,
        port=instance.port,
        database_name=instance.database_name,
        environment=instance.environment,
        has_collect_dsn=bool(instance.encrypted_collect_dsn),
        has_kill_dsn=instance.encrypted_kill_dsn is not None,
        status=instance.status,
        collect_interval_seconds=instance.collect_interval_seconds,
        retention_days=instance.retention_days,
        business_owner=instance.business_owner,
        dba_owner=instance.dba_owner,
        sqlserver_version=instance.sqlserver_version,
        created_at=instance.created_at,
        updated_at=instance.updated_at,
    )


async def list_instances(session: AsyncSession) -> list[InstanceOut]:
    result = await session.execute(
        select(Instance)
        .where(Instance.status != "disabled")
        .order_by(Instance.created_at.desc())
    )
    return [
        _to_instance_out(instance)
        for instance in result.scalars().all()
        if instance.status != "disabled"
    ]


async def create_instance(session: AsyncSession, data: InstanceCreate) -> InstanceOut:
    collect_dsn = data.collect_dsn or build_sql_auth_connection_string(
        host=data.host,
        port=data.port,
        username=data.username or "",
        password=data.password or "",
        database_name=data.database_name or "master",
    )
    instance = Instance(
        id=uuid.uuid4(),
        name=data.name,
        host=data.host,
        port=data.port,
        database_name=data.database_name,
        environment=data.environment,
        encrypted_collect_dsn=encrypt_connection_string(collect_dsn),
        encrypted_kill_dsn=encrypt_connection_string(data.kill_dsn) if data.kill_dsn else None,
        status=data.status,
        collect_interval_seconds=data.collect_interval_seconds,
        retention_days=data.retention_days,
        business_owner=data.business_owner,
        dba_owner=data.dba_owner,
        sqlserver_version=data.sqlserver_version,
    )
    session.add(instance)
    session.add(
        InstanceCollectStatus(
            instance_id=instance.id,
            consecutive_failures=0,
            status="unknown",
            capabilities={},
        )
    )
    await session.commit()
    await session.refresh(instance)
    return _to_instance_out(instance)


async def update_instance(
    session: AsyncSession,
    instance_id: uuid.UUID,
    data: InstanceUpdate,
) -> InstanceOut | None:
    instance = await session.get(Instance, instance_id)
    if instance is None:
        return None

    fields_set = data.model_fields_set
    payload = data.model_dump(exclude_unset=True)

    for field_name in (
        "name",
        "host",
        "port",
        "database_name",
        "environment",
        "status",
        "collect_interval_seconds",
        "retention_days",
        "business_owner",
        "dba_owner",
        "sqlserver_version",
    ):
        if field_name in fields_set:
            setattr(instance, field_name, payload[field_name])

    if "collect_dsn" in fields_set:
        collect_dsn = payload["collect_dsn"]
        if collect_dsn is not None:
            instance.encrypted_collect_dsn = encrypt_connection_string(collect_dsn)
    elif data.username and data.password:
        instance.encrypted_collect_dsn = encrypt_connection_string(
            build_sql_auth_connection_string(
                host=instance.host,
                port=instance.port,
                username=data.username,
                password=data.password,
                database_name=instance.database_name or "master",
            )
        )

    if "kill_dsn" in fields_set:
        kill_dsn = payload["kill_dsn"]
        if kill_dsn is None:
            instance.encrypted_kill_dsn = None
        else:
            instance.encrypted_kill_dsn = encrypt_connection_string(kill_dsn)

    await session.commit()
    await session.refresh(instance)
    return _to_instance_out(instance)


async def delete_instance(session: AsyncSession, instance_id: uuid.UUID) -> bool:
    instance = await session.get(Instance, instance_id)
    if instance is None:
        return False

    instance.status = "disabled"
    await session.commit()
    await session.refresh(instance)
    return True
