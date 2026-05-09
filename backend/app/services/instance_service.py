from __future__ import annotations

import base64
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Instance, InstanceCollectStatus
from app.schemas.instances import InstanceCreate, InstanceOut, InstanceUpdate


def encrypt_connection_string(connection_string: str) -> str:
    # P0 占位实现：仅用于接口打通，后续需替换为真实加密/KMS。
    return base64.b64encode(connection_string.encode("utf-8")).decode("ascii")


def decrypt_connection_string(encrypted_connection_string: str) -> str:
    # P0 占位实现：仅用于接口打通，后续需替换为真实解密/KMS。
    return base64.b64decode(encrypted_connection_string.encode("ascii")).decode("utf-8")


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
    result = await session.execute(select(Instance).order_by(Instance.created_at.desc()))
    return [_to_instance_out(instance) for instance in result.scalars().all()]


async def create_instance(session: AsyncSession, data: InstanceCreate) -> InstanceOut:
    instance = Instance(
        id=uuid.uuid4(),
        name=data.name,
        host=data.host,
        port=data.port,
        database_name=data.database_name,
        environment=data.environment,
        encrypted_collect_dsn=encrypt_connection_string(data.collect_dsn),
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

    if "kill_dsn" in fields_set:
        kill_dsn = payload["kill_dsn"]
        if kill_dsn is None:
            instance.encrypted_kill_dsn = None
        else:
            instance.encrypted_kill_dsn = encrypt_connection_string(kill_dsn)

    await session.commit()
    await session.refresh(instance)
    return _to_instance_out(instance)
