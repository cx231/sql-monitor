from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi import Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_roles
from app.db.models import User
from app.db.postgres import async_session_factory
from app.schemas.indexes import (
    IndexCreateRequest,
    IndexCreateResponse,
    IndexAuditOut,
    IndexFragmentationActionRequest,
    IndexFragmentationActionResponse,
    IndexFragmentationItem,
    IndexFragmentationListOut,
    IndexDatabaseListOut,
    MissingIndexItem,
    MissingIndexListOut,
)
from app.services.index_service import (
    CreateIndexRequestData,
    FragmentationActionRequestData,
    IndexNameConflictError,
    create_missing_index,
    execute_fragmentation_action,
    get_index_fragmentation,
    get_index_audit,
    get_missing_indexes,
    get_user_databases,
    run_fragmentation_ddl,
    run_missing_index_ddl,
)

router = APIRouter(prefix="/indexes", tags=["indexes"])


@router.get("/audits/{audit_id}", response_model=IndexAuditOut)
async def get_index_audit_route(
    audit_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles(["developer", "dba", "admin"])),
) -> IndexAuditOut:
    audit = await get_index_audit(session, audit_id)
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AUDIT_NOT_FOUND")
    return audit


@router.get("/databases", response_model=IndexDatabaseListOut)
async def get_index_databases(
    instance_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles(["developer", "dba", "admin"])),
) -> IndexDatabaseListOut:
    databases = await get_user_databases(session, instance_id)
    if databases is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="INSTANCE_NOT_FOUND")
    return IndexDatabaseListOut(instance_id=instance_id, databases=databases)


@router.get("/missing", response_model=MissingIndexListOut)
async def get_missing_index_list(
    instance_id: uuid.UUID,
    database_name: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles(["developer", "dba", "admin"])),
) -> MissingIndexListOut:
    try:
        result = await get_missing_indexes(
            session,
            instance_id,
            database_name,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="INSTANCE_NOT_FOUND")
    return MissingIndexListOut(
        instance_id=instance_id,
        database_name=database_name,
        checked_at=result.checked_at,
        collection_status=result.collection_status,
        collection_error=result.collection_error,
        stale=result.stale,
        page=page,
        page_size=page_size,
        total=result.total,
        items=[MissingIndexItem(**item.__dict__) for item in result.items],
    )


@router.get("/fragmentation", response_model=IndexFragmentationListOut)
async def get_index_fragmentation_list(
    instance_id: uuid.UUID,
    database_name: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles(["developer", "dba", "admin"])),
) -> IndexFragmentationListOut:
    try:
        result = await get_index_fragmentation(
            session,
            instance_id,
            database_name,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="INSTANCE_NOT_FOUND")
    items = result.items
    online_supported = any(item.online_rebuild_supported for item in items)
    return IndexFragmentationListOut(
        instance_id=instance_id,
        database_name=database_name,
        checked_at=result.checked_at,
        collection_status=result.collection_status,
        collection_error=result.collection_error,
        stale=result.stale,
        online_rebuild_supported=online_supported,
        page=page,
        page_size=page_size,
        total=result.total,
        items=[IndexFragmentationItem(**item.__dict__) for item in items],
    )


@router.post("", response_model=IndexCreateResponse)
async def post_index(
    request: IndexCreateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_roles(["dba", "admin"])),
) -> IndexCreateResponse:
    try:
        response = await create_missing_index(
            session,
            CreateIndexRequestData(
                instance_id=request.instance_id,
                database_name=request.database_name,
                schema_name=request.schema_name,
                table_name=request.table_name,
                key_columns=request.key_columns,
                include_columns=request.include_columns,
                index_name=request.index_name,
            ),
            operator=user,
        )
        background_tasks.add_task(_run_missing_index_ddl_task, response.audit_id)
        return response
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="INSTANCE_NOT_FOUND")
    except IndexNameConflictError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="INDEX_NAME_CONFLICT")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/fragmentation/actions", response_model=IndexFragmentationActionResponse)
async def post_index_fragmentation_action(
    request: IndexFragmentationActionRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_roles(["dba", "admin"])),
) -> IndexFragmentationActionResponse:
    try:
        response = await execute_fragmentation_action(
            session,
            FragmentationActionRequestData(
                instance_id=request.instance_id,
                database_name=request.database_name,
                schema_name=request.schema_name,
                table_name=request.table_name,
                index_name=request.index_name,
                partition_number=request.partition_number,
                action=request.action,
                avg_fragmentation_in_percent=request.avg_fragmentation_in_percent,
                page_count=request.page_count,
            ),
            operator=user,
        )
        background_tasks.add_task(_run_fragmentation_ddl_task, response.audit_id)
        return response
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="INSTANCE_NOT_FOUND")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


async def _run_missing_index_ddl_task(audit_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        await run_missing_index_ddl(session, audit_id)


async def _run_fragmentation_ddl_task(audit_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        await run_fragmentation_ddl(session, audit_id)
