"""创建默认管理员用户。"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.dialects.postgresql import UUID

from app.security import hash_password


revision = "0002_seed_default_admin_user"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "Admin@2026"
DEFAULT_ADMIN_DISPLAY_NAME = "系统管理员"
DEFAULT_ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")

users_table = sa.table(
    "users",
    sa.column("id", UUID(as_uuid=True)),
    sa.column("username", sa.String(length=128)),
    sa.column("password_hash", sa.Text()),
    sa.column("display_name", sa.String(length=128)),
    sa.column("role", sa.String(length=32)),
    sa.column("status", sa.String(length=32)),
)


def default_admin_values() -> dict[str, object]:
    return {
        "id": DEFAULT_ADMIN_ID,
        "username": DEFAULT_ADMIN_USERNAME,
        "password_hash": hash_password(DEFAULT_ADMIN_PASSWORD),
        "display_name": DEFAULT_ADMIN_DISPLAY_NAME,
        "role": "admin",
        "status": "active",
    }


def build_default_admin_insert(
    *,
    user_id: uuid.UUID,
    password_hash: str,
):
    return (
        insert(users_table)
        .values(
            id=user_id,
            username=DEFAULT_ADMIN_USERNAME,
            password_hash=password_hash,
            display_name=DEFAULT_ADMIN_DISPLAY_NAME,
            role="admin",
            status="active",
        )
        .on_conflict_do_nothing(index_elements=["username"])
    )


def upgrade() -> None:
    values = default_admin_values()
    op.execute(
        build_default_admin_insert(
            user_id=values["id"],
            password_hash=values["password_hash"],
        )
    )


def downgrade() -> None:
    op.execute(
        build_default_admin_delete()
    )


def build_default_admin_delete():
    return users_table.delete().where(
        sa.and_(
            users_table.c.id == DEFAULT_ADMIN_ID,
            users_table.c.username == DEFAULT_ADMIN_USERNAME,
        )
    )
