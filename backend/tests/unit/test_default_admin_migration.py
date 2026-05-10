from __future__ import annotations

import importlib
import uuid

from sqlalchemy.dialects import postgresql

from app.security import verify_password


def test_default_admin_migration_hashes_configured_password() -> None:
    migration = importlib.import_module(
        "app.db.migrations.versions.0002_seed_default_admin_user"
    )

    values = migration.default_admin_values()

    assert values["id"] == migration.DEFAULT_ADMIN_ID
    assert values["username"] == "admin"
    assert values["display_name"] == "系统管理员"
    assert values["role"] == "admin"
    assert values["status"] == "active"
    assert values["password_hash"] != "Admin@2026"
    assert verify_password("Admin@2026", values["password_hash"]) is True


def test_default_admin_insert_is_idempotent() -> None:
    migration = importlib.import_module(
        "app.db.migrations.versions.0002_seed_default_admin_user"
    )

    statement = migration.build_default_admin_insert(
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        password_hash="hashed-password",
    )
    compiled = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "INSERT INTO users" in compiled
    assert "ON CONFLICT (username) DO NOTHING" in compiled


def test_default_admin_delete_only_targets_seed_user() -> None:
    migration = importlib.import_module(
        "app.db.migrations.versions.0002_seed_default_admin_user"
    )

    statement = migration.build_default_admin_delete()
    compiled = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "DELETE FROM users" in compiled
    assert "00000000-0000-0000-0000-000000000002" in compiled
    assert "admin" in compiled
