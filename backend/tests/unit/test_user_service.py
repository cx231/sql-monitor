from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

from app.api.deps import current_user, get_db_session
from app.db.models import User
from app.security import hash_password, verify_password
from app.services.auth_service import authenticate_user
from app.services.user_service import (
    create_user,
    disable_user,
    list_users,
    reset_user_password,
    update_user,
)


def _user(
    *,
    user_id: uuid.UUID | None = None,
    username: str = "alice",
    role: str = "viewer",
    status: str = "active",
    password: str = "secret",
):
    return User(
        id=user_id or uuid.uuid4(),
        username=username,
        password_hash=hash_password(password),
        display_name=username.title(),
        role=role,
        status=status,
    )


def _fake_current_user(role: str = "admin", user_id: uuid.UUID | None = None):
    return SimpleNamespace(
        id=user_id or uuid.uuid4(),
        username=f"{role}_user",
        password_hash="hash",
        role=role,
        status="active",
    )


def test_list_users_orders_by_username() -> None:
    users = [_user(username="zoe"), _user(username="alice")]

    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return users

    class FakeSession:
        async def execute(self, statement):
            return FakeResult()

    result = asyncio.run(list_users(FakeSession()))

    assert result == users


def test_create_user_hashes_password_and_defaults_active() -> None:
    added = []

    class FakeSession:
        def add(self, obj):
            added.append(obj)

        async def commit(self):
            pass

        async def refresh(self, obj):
            pass

    result = asyncio.run(
        create_user(
            FakeSession(),
            username="alice",
            password="NewPassword123!",
            display_name="Alice",
            role="developer",
        )
    )

    assert added == [result]
    assert result.username == "alice"
    assert result.display_name == "Alice"
    assert result.role == "developer"
    assert result.status == "active"
    assert result.password_hash != "NewPassword123!"
    assert verify_password("NewPassword123!", result.password_hash) is True


def test_update_user_edits_profile_role_and_status() -> None:
    user = _user(role="viewer", status="active")

    class FakeSession:
        async def get(self, model, user_id):
            return user

        async def commit(self):
            pass

        async def refresh(self, obj):
            pass

    result = asyncio.run(
        update_user(
            FakeSession(),
            user.id,
            display_name="Alice DBA",
            role="dba",
            status="disabled",
        )
    )

    assert result is user
    assert user.display_name == "Alice DBA"
    assert user.role == "dba"
    assert user.status == "disabled"


def test_disable_user_sets_disabled_status() -> None:
    user = _user(status="active")

    class FakeSession:
        async def get(self, model, user_id):
            return user

        async def commit(self):
            pass

        async def refresh(self, obj):
            pass

    result = asyncio.run(disable_user(FakeSession(), user.id, operator_user_id=uuid.uuid4()))

    assert result is user
    assert user.status == "disabled"


def test_disable_user_rejects_current_user() -> None:
    user_id = uuid.uuid4()
    user = _user(user_id=user_id)

    class FakeSession:
        async def get(self, model, requested_id):
            return user

    result = asyncio.run(disable_user(FakeSession(), user_id, operator_user_id=user_id))

    assert result is None
    assert user.status == "active"


def test_reset_user_password_hashes_new_password() -> None:
    user = _user(password="old-password")

    class FakeSession:
        async def get(self, model, user_id):
            return user

        async def commit(self):
            pass

        async def refresh(self, obj):
            pass

    result = asyncio.run(reset_user_password(FakeSession(), user.id, "NewPassword123!"))

    assert result is user
    assert verify_password("old-password", user.password_hash) is False
    assert verify_password("NewPassword123!", user.password_hash) is True


def test_disabled_user_cannot_login_after_disable() -> None:
    user = _user(status="disabled", password="secret")

    class FakeSession:
        async def scalar(self, statement):
            return user

    result = asyncio.run(authenticate_user(FakeSession(), "alice", "secret"))

    assert result is None


def test_user_routes_require_admin(api_client) -> None:
    app = api_client.app
    app.dependency_overrides[get_db_session] = lambda: None
    app.dependency_overrides[current_user] = lambda: _fake_current_user("dba")

    response = api_client.get("/api/users")

    assert response.status_code == 403
    app.dependency_overrides.clear()


def test_create_user_route_returns_created_user(api_client) -> None:
    class FakeSession:
        def add(self, obj):
            self.user = obj

        async def commit(self):
            pass

        async def refresh(self, obj):
            pass

    app = api_client.app
    app.dependency_overrides[get_db_session] = lambda: FakeSession()
    app.dependency_overrides[current_user] = lambda: _fake_current_user("admin")

    response = api_client.post(
        "/api/users",
        json={
            "username": "alice",
            "password": "NewPassword123!",
            "display_name": "Alice",
            "role": "developer",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["username"] == "alice"
    assert payload["display_name"] == "Alice"
    assert payload["role"] == "developer"
    assert payload["status"] == "active"
    assert "password" not in payload
    assert "password_hash" not in payload
    app.dependency_overrides.clear()


def test_disable_user_route_rejects_self_disable(api_client) -> None:
    user_id = uuid.uuid4()
    user = _user(user_id=user_id)

    class FakeSession:
        async def get(self, model, requested_id):
            return user

    app = api_client.app
    app.dependency_overrides[get_db_session] = lambda: FakeSession()
    app.dependency_overrides[current_user] = lambda: _fake_current_user("admin", user_id=user_id)

    response = api_client.post(f"/api/users/{user_id}/disable")

    assert response.status_code == 400
    assert response.json()["detail"] == "不能禁用当前登录用户"
    assert user.status == "active"
    app.dependency_overrides.clear()


def test_update_user_route_rejects_self_disable(api_client) -> None:
    user_id = uuid.uuid4()
    user = _user(user_id=user_id)

    class FakeSession:
        async def get(self, model, requested_id):
            return user

    app = api_client.app
    app.dependency_overrides[get_db_session] = lambda: FakeSession()
    app.dependency_overrides[current_user] = lambda: _fake_current_user("admin", user_id=user_id)

    response = api_client.put(
        f"/api/users/{user_id}",
        json={
            "display_name": "Admin",
            "role": "admin",
            "status": "disabled",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "不能禁用当前登录用户"
    assert user.status == "active"
    app.dependency_overrides.clear()
