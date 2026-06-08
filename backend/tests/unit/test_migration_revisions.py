from __future__ import annotations

import ast
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "app" / "db" / "migrations" / "versions"


def test_alembic_revision_ids_fit_default_version_table() -> None:
    for migration_path in MIGRATIONS_DIR.glob("*.py"):
        module = ast.parse(migration_path.read_text())
        revision = _assigned_string(module, "revision")

        assert revision is not None, f"{migration_path.name} missing revision"
        assert len(revision) <= 32, f"{migration_path.name} revision id exceeds Alembic varchar(32)"


def _assigned_string(module: ast.Module, name: str) -> str | None:
    for statement in module.body:
        if not isinstance(statement, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in statement.targets):
            continue
        if isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
            return statement.value.value
    return None
