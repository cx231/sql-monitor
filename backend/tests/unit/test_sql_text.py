from __future__ import annotations

from app.collector.sql_text import normalize_sql, normalized_sql_hash, preview_sql, sql_hash


def test_preview_sql_compresses_whitespace() -> None:
    assert preview_sql("SELECT   *\nFROM\torders") == "SELECT * FROM orders"


def test_preview_sql_truncates_long_sql() -> None:
    assert preview_sql("SELECT " + "x" * 80, max_length=20) == "SELECT xxxxxxxxxx..."


def test_normalize_sql_replaces_literals_and_lowercases() -> None:
    assert normalize_sql("SELECT * FROM T WHERE id = 42 AND name = 'Alice'") == (
        "select * from t where id = ? and name = ?"
    )


def test_sql_hash_changes_with_original_sql() -> None:
    assert sql_hash("SELECT 1") != sql_hash("SELECT 2")


def test_normalized_sql_hash_ignores_literal_values() -> None:
    assert normalized_sql_hash("SELECT 1") == normalized_sql_hash("select 2")
