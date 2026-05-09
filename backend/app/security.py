from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.config import get_settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    subject: str,
    role: str,
    additional_claims: Optional[Mapping[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    settings = get_settings()
    expire_at = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "exp": expire_at,
    }
    if additional_claims:
        payload.update(additional_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except InvalidTokenError as exc:
        raise ValueError("无效的访问令牌") from exc
    if payload.get("type") != "access":
        raise ValueError("无效的令牌类型")
    return payload
