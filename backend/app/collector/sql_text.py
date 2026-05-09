from __future__ import annotations

import hashlib
import re
from typing import Optional

_WHITESPACE_RE = re.compile(r"\s+")
_SINGLE_QUOTED_STRING_RE = re.compile(r"'(?:''|[^'])*'")
_NUMERIC_LITERAL_RE = re.compile(r"\b\d+(?:\.\d+)?\b")


def _collapse_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def preview_sql(sql_text: Optional[str], max_length: int = 120) -> str:
    if not sql_text:
        return ""
    preview = _collapse_whitespace(sql_text)
    if len(preview) <= max_length:
        return preview
    if max_length <= 3:
        return "..."[:max_length]
    return preview[: max_length - 3].rstrip() + "..."


def normalize_sql(sql_text: Optional[str]) -> str:
    if not sql_text:
        return ""
    normalized = sql_text.lower()
    normalized = _collapse_whitespace(normalized)
    normalized = _SINGLE_QUOTED_STRING_RE.sub("?", normalized)
    normalized = _NUMERIC_LITERAL_RE.sub("?", normalized)
    normalized = _collapse_whitespace(normalized)
    return normalized


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sql_hash(sql_text: Optional[str]) -> str:
    return _sha256_hex(sql_text or "")


def normalized_sql_hash(sql_text: Optional[str]) -> str:
    return _sha256_hex(normalize_sql(sql_text))
