from __future__ import annotations

import asyncio
import uuid

import jwt
import pytest
from fastapi import HTTPException

from app.api.deps import require_roles
from app.config import Settings, get_settings
from app.db.models import User
from app.security import ALGORITHM, create_access_token, decode_access_token, hash_password, verify_password
from app.services.auth_service import authenticate_user


def test_password_hash_verification() -> None:
    password_hash = hash_password("correct-horse-battery-staple")

    assert password_hash != "correct-horse-battery-staple"
    assert verify_password("correct-horse-battery-staple", password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_access_token_round_trip(monkeypatch) -> None:
    monkeypatch.setenv("SQLMON_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
    get_settings.cache_clear()
    user_id = uuid.uuid4()

    token = create_access_token(
        subject=str(user_id),
        role="dba",
        additional_claims={"username": "alice"},
    )
    payload = decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["role"] == "dba"
    assert payload["username"] == "alice"
    assert payload["type"] == "access"
    assert "exp" in payload
    get_settings.cache_clear()


@pytest.mark.parametrize("reserved_claim", ["exp", "sub", "type"])
def test_access_token_additional_claims_cannot_override_reserved_claims(
    monkeypatch,
    reserved_claim: str,
) -> None:
    monkeypatch.setenv("SQLMON_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
    get_settings.cache_clear()

    with pytest.raises(ValueError):
        create_access_token(
            subject=str(uuid.uuid4()),
            role="dba",
            additional_claims={reserved_claim: "override"},
        )

    get_settings.cache_clear()


def test_decode_access_token_rejects_missing_exp(monkeypatch) -> None:
    secret_key = "test-secret-key-with-at-least-32-bytes"
    monkeypatch.setenv("SQLMON_SECRET_KEY", secret_key)
    get_settings.cache_clear()
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "access", "role": "dba"},
        secret_key,
        algorithm=ALGORITHM,
    )

    with pytest.raises(ValueError):
        decode_access_token(token)

    get_settings.cache_clear()


@pytest.mark.parametrize(
    "claims",
    [
        {"type": "access", "role": "dba", "exp": 4_102_444_800},
        {"sub": str(uuid.uuid4()), "role": "dba", "exp": 4_102_444_800},
        {"sub": "", "type": "access", "role": "dba", "exp": 4_102_444_800},
        {"sub": 123, "type": "access", "role": "dba", "exp": 4_102_444_800},
    ],
)
def test_decode_access_token_rejects_invalid_subject_or_missing_type(
    monkeypatch,
    claims: dict[str, object],
) -> None:
    secret_key = "test-secret-key-with-at-least-32-bytes"
    monkeypatch.setenv("SQLMON_SECRET_KEY", secret_key)
    get_settings.cache_clear()
    token = jwt.encode(claims, secret_key, algorithm=ALGORITHM)

    with pytest.raises(ValueError):
        decode_access_token(token)

    get_settings.cache_clear()


def test_decode_access_token_rejects_non_access_type(monkeypatch) -> None:
    secret_key = "test-secret-key-with-at-least-32-bytes"
    monkeypatch.setenv("SQLMON_SECRET_KEY", secret_key)
    get_settings.cache_clear()
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "refresh", "role": "dba", "exp": 4_102_444_800},
        secret_key,
        algorithm=ALGORITHM,
    )

    with pytest.raises(ValueError):
        decode_access_token(token)

    get_settings.cache_clear()


def test_non_production_settings_allow_default_secret() -> None:
    settings = Settings(env="test")

    assert settings.secret_key == "dev-secret-key"


def test_production_settings_reject_weak_secret() -> None:
    with pytest.raises(ValueError):
        Settings(env="prod", secret_key="short")


def test_production_settings_reject_default_secret() -> None:
    with pytest.raises(ValueError):
        Settings(env="prod", secret_key="dev-secret-key")


def test_authenticate_user_returns_active_user_for_valid_password() -> None:
    user = User(
        id=uuid.uuid4(),
        username="alice",
        password_hash=hash_password("secret"),
        display_name="Alice",
        role="dba",
        status="active",
    )

    class FakeSession:
        async def scalar(self, statement):
            return user

    result = asyncio.run(authenticate_user(FakeSession(), "alice", "secret"))

    assert result is user


def test_authenticate_user_rejects_wrong_password() -> None:
    user = User(
        id=uuid.uuid4(),
        username="alice",
        password_hash=hash_password("secret"),
        display_name="Alice",
        role="dba",
        status="active",
    )

    class FakeSession:
        async def scalar(self, statement):
            return user

    result = asyncio.run(authenticate_user(FakeSession(), "alice", "wrong"))

    assert result is None


def test_authenticate_user_rejects_disabled_user() -> None:
    user = User(
        id=uuid.uuid4(),
        username="alice",
        password_hash=hash_password("secret"),
        display_name="Alice",
        role="dba",
        status="disabled",
    )

    class FakeSession:
        async def scalar(self, statement):
            return user

    result = asyncio.run(authenticate_user(FakeSession(), "alice", "secret"))

    assert result is None


def test_require_roles_returns_user_when_role_allowed() -> None:
    user = User(
        id=uuid.uuid4(),
        username="alice",
        password_hash="hash",
        role="dba",
        status="active",
    )

    dependency = require_roles(["dba", "admin"])

    assert dependency(user) is user


def test_require_roles_rejects_user_when_role_not_allowed() -> None:
    user = User(
        id=uuid.uuid4(),
        username="alice",
        password_hash="hash",
        role="viewer",
        status="active",
    )

    dependency = require_roles(["dba", "admin"])

    with pytest.raises(HTTPException) as exc_info:
        dependency(user)

    assert exc_info.value.status_code == 403
