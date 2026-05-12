from __future__ import annotations

import asyncio
import uuid

import jwt
import pytest
from fastapi import HTTPException

from app.api.deps import require_roles
from app.api.deps import get_db_session
from app.config import Settings, get_settings
from app.db.models import User
from app.security import ALGORITHM, create_access_token, decode_access_token, hash_password, verify_password
from app.services.auth_service import authenticate_user
from app.services.captcha_service import (
    create_captcha_challenge,
    generate_captcha_code,
    verify_captcha,
)


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


def test_generate_captcha_code_returns_six_digits() -> None:
    code = generate_captcha_code()

    assert len(code) == 6
    assert code.isdigit()


def test_captcha_challenge_verifies_correct_code(monkeypatch) -> None:
    monkeypatch.setenv("SQLMON_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
    get_settings.cache_clear()

    challenge = create_captcha_challenge(code="123456")

    assert challenge.captcha_token
    assert challenge.image_data_url.startswith("data:image/svg+xml;base64,")
    assert challenge.expires_in_seconds == 300
    assert verify_captcha(challenge.captcha_token, "123456") is True
    get_settings.cache_clear()


def test_captcha_challenge_rejects_wrong_code(monkeypatch) -> None:
    monkeypatch.setenv("SQLMON_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
    get_settings.cache_clear()
    challenge = create_captcha_challenge(code="123456")

    assert verify_captcha(challenge.captcha_token, "654321") is False
    assert verify_captcha(challenge.captcha_token, "abc123") is False
    get_settings.cache_clear()


def test_captcha_challenge_rejects_malformed_token() -> None:
    assert verify_captcha("not-a-token", "123456") is False


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


def test_captcha_route_returns_token_and_image(api_client, monkeypatch) -> None:
    monkeypatch.setenv("SQLMON_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
    get_settings.cache_clear()

    response = api_client.get("/api/auth/captcha")

    assert response.status_code == 200
    payload = response.json()
    assert payload["captcha_token"]
    assert payload["image_data_url"].startswith("data:image/svg+xml;base64,")
    assert payload["expires_in_seconds"] == 300
    assert "captcha_code" not in payload
    get_settings.cache_clear()


def test_login_route_rejects_missing_captcha(api_client) -> None:
    response = api_client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "secret"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "验证码错误或已过期"


def test_login_route_rejects_wrong_captcha(api_client, monkeypatch) -> None:
    monkeypatch.setenv("SQLMON_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
    get_settings.cache_clear()
    challenge = create_captcha_challenge(code="123456")

    response = api_client.post(
        "/api/auth/login",
        json={
            "username": "alice",
            "password": "secret",
            "captcha_token": challenge.captcha_token,
            "captcha_code": "654321",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "验证码错误或已过期"
    get_settings.cache_clear()


def test_login_route_accepts_valid_captcha_and_credentials(api_client, monkeypatch) -> None:
    monkeypatch.setenv("SQLMON_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
    get_settings.cache_clear()
    user = User(
        id=uuid.uuid4(),
        username="alice",
        password_hash=hash_password("secret"),
        display_name="Alice",
        role="dba",
        status="active",
    )
    challenge = create_captcha_challenge(code="123456")

    class FakeSession:
        async def scalar(self, statement):
            return user

    app = api_client.app
    app.dependency_overrides[get_db_session] = lambda: FakeSession()

    response = api_client.post(
        "/api/auth/login",
        json={
            "username": "alice",
            "password": "secret",
            "captcha_token": challenge.captcha_token,
            "captcha_code": "123456",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["access_token"]
    assert payload["username"] == "alice"
    assert payload["role"] == "dba"
    app.dependency_overrides.clear()
    get_settings.cache_clear()
