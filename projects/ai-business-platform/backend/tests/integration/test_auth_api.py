from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.core.security import create_access_token
from app.main import create_app
from app.modules.users.models import User

import httpx

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/users/me"

PASSWORD = "S3cure-password!"


async def _register(client, email="alice@example.com", password=PASSWORD, full_name="Alice"):
    return await client.post(
        REGISTER, json={"email": email, "password": password, "full_name": full_name}
    )


async def _login(client, email="alice@example.com", password=PASSWORD):
    return await client.post(LOGIN, json={"email": email, "password": password})


async def _token(client, email="alice@example.com") -> str:
    await _register(client, email=email)
    return (await _login(client, email=email)).json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- register --------------------------------------------------------------------------


async def test_register_creates_user_with_least_privileged_role(api_client):
    response = await _register(api_client, email="Alice@Example.COM")

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"  # normalised
    assert body["roles"] == ["employee"]
    assert "password" not in body and "password_hash" not in body


async def test_register_duplicate_email_is_conflict_even_with_different_case(api_client):
    await _register(api_client, email="alice@example.com")

    response = await _register(api_client, email="ALICE@example.com")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "alice@example.com", "password": "short", "full_name": "A"},  # < 8 chars
        {"email": "alice@example.com", "password": "x" * 129, "full_name": "A"},  # > 128
        {"email": "not-an-email", "password": PASSWORD, "full_name": "A"},
        {"email": "alice@example.com", "password": PASSWORD, "full_name": "   "},
        {"email": "alice@example.com", "password": PASSWORD},  # no full_name
    ],
)
async def test_register_rejects_invalid_input(api_client, payload):
    response = await api_client.post(REGISTER, json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_password_is_stored_hashed(api_client, session):
    await _register(api_client)

    user = (await session.execute(select(User))).scalar_one()

    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash


# --- login -----------------------------------------------------------------------------


async def test_login_returns_bearer_token_and_updates_last_login(api_client, session):
    await _register(api_client)

    response = await _login(api_client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().access_token_expire_minutes * 60
    user = (await session.execute(select(User))).scalar_one()
    assert user.last_login_at is not None


async def test_wrong_password_and_unknown_email_give_identical_errors(api_client):
    await _register(api_client)

    wrong_password = await _login(api_client, password="not-the-password")
    unknown_email = await _login(api_client, email="nobody@example.com")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["error"]["message"] == unknown_email.json()["error"]["message"]
    assert wrong_password.headers["WWW-Authenticate"] == "Bearer"


async def test_inactive_user_cannot_log_in(api_client, session):
    await _register(api_client)
    user = (await session.execute(select(User))).scalar_one()
    user.is_active = False
    await session.commit()

    response = await _login(api_client)

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password"


# --- authenticated access --------------------------------------------------------------


async def test_me_returns_profile_with_roles_and_permissions(api_client):
    token = await _token(api_client)

    response = await api_client.get(ME, headers=_auth(token))

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["roles"] == ["employee"]
    assert "customer:read" in body["permissions"]
    assert "customer:update" not in body["permissions"]


async def test_me_without_token_is_401(api_client):
    response = await api_client.get(ME)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "unauthorized"


async def test_me_with_garbage_token_is_401(api_client):
    response = await api_client.get(ME, headers=_auth("garbage"))

    assert response.status_code == 401


async def test_expired_token_is_401(api_client, session):
    await _register(api_client)
    user = (await session.execute(select(User))).scalar_one()
    settings = get_settings()
    token, _ = create_access_token(
        user.id,
        secret_key=settings.secret_key,
        algorithm=settings.jwt_algorithm,
        expires_minutes=5,
        now=datetime.now(UTC) - timedelta(hours=1),
    )

    response = await api_client.get(ME, headers=_auth(token))

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Token has expired"


async def test_token_of_a_deleted_user_is_401(api_client, session):
    token = await _token(api_client)
    await session.delete((await session.execute(select(User))).scalar_one())
    await session.commit()

    assert (await api_client.get(ME, headers=_auth(token))).status_code == 401


async def test_disabling_a_user_invalidates_existing_tokens(api_client, session):
    token = await _token(api_client)
    user = (await session.execute(select(User))).scalar_one()
    user.is_active = False
    await session.commit()

    assert (await api_client.get(ME, headers=_auth(token))).status_code == 401


# --- logout ----------------------------------------------------------------------------


async def test_logout_revokes_only_that_token(api_client):
    first = await _token(api_client)
    second = (await _login(api_client)).json()["access_token"]  # same user, new token

    assert (await api_client.post(LOGOUT, headers=_auth(first))).status_code == 204

    revoked = await api_client.get(ME, headers=_auth(first))
    assert revoked.status_code == 401
    assert revoked.json()["error"]["message"] == "Token has been revoked"
    assert (await api_client.get(ME, headers=_auth(second))).status_code == 200


async def test_logout_twice_fails_the_second_time(api_client):
    token = await _token(api_client)

    assert (await api_client.post(LOGOUT, headers=_auth(token))).status_code == 204
    assert (await api_client.post(LOGOUT, headers=_auth(token))).status_code == 401


async def test_logout_requires_authentication(api_client):
    assert (await api_client.post(LOGOUT)).status_code == 401


# --- failure of a dependency -----------------------------------------------------------


async def test_authentication_fails_closed_when_redis_is_down(api_client, session, test_database_url):
    await _register(api_client)
    user = (await session.execute(select(User))).scalar_one()
    settings = get_settings().model_copy(
        update={
            "database_url": test_database_url,
            "redis_url": "redis://127.0.0.1:1/0",  # nothing listens on port 1
        }
    )
    token, _ = create_access_token(
        user.id,
        secret_key=settings.secret_key,
        algorithm=settings.jwt_algorithm,
        expires_minutes=5,
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(ME, headers=_auth(token))

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
