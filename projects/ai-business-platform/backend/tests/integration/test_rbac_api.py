import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from app.core.database import create_engine, create_session_factory
from app.core.exceptions import ConflictError
from app.core.permissions import ROLE_ADMIN
from app.core.security import hash_password
from app.modules.auth.models import Role
from app.modules.users.create_admin import ensure_admin
from app.modules.users.models import User
from app.modules.users.service import UserService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

PASSWORD = "S3cure-password!"
USERS = "/api/v1/users"
ROLES = "/api/v1/roles"


async def make_user(session, email: str, role: str) -> User:
    """Create a user directly in the DB with one role (bypasses the API on purpose)."""
    role_obj = (await session.execute(select(Role).where(Role.name == role))).scalar_one()
    user = User(email=email, password_hash=hash_password(PASSWORD), full_name=email.split("@")[0])
    user.roles.append(role_obj)
    session.add(user)
    await session.commit()
    return user


async def auth_for(client, user: User) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def admin(api_client, session):
    user = await make_user(session, "admin@example.com", "admin")
    return user, await auth_for(api_client, user)


@pytest.fixture
async def employee(api_client, session):
    user = await make_user(session, "emp@example.com", "employee")
    return user, await auth_for(api_client, user)


# --- 401 vs 403 ------------------------------------------------------------------------


async def test_no_token_is_401_not_403(api_client):
    assert (await api_client.get(USERS)).status_code == 401


async def test_authenticated_without_permission_is_403(api_client, employee):
    response = await api_client.get(USERS, headers=employee[1])

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert "user:read" not in response.text  # does not reveal which permission was missing


async def test_manager_can_read_but_not_manage_users(api_client, session, admin, employee):
    manager = await make_user(session, "mgr@example.com", "manager")
    headers = await auth_for(api_client, manager)

    assert (await api_client.get(USERS, headers=headers)).status_code == 200
    response = await api_client.put(
        f"{USERS}/{employee[0].id}/roles", json={"roles": ["sales"]}, headers=headers
    )
    assert response.status_code == 403


# --- user listing ----------------------------------------------------------------------


async def test_list_users_with_pagination(api_client, session, admin):
    for i in range(3):
        await make_user(session, f"user{i}@example.com", "employee")

    page = await api_client.get(USERS, params={"limit": 2, "offset": 0}, headers=admin[1])
    rest = await api_client.get(USERS, params={"limit": 2, "offset": 2}, headers=admin[1])

    assert page.json()["total"] == 4 and len(page.json()["items"]) == 2
    assert len(rest.json()["items"]) == 2
    ids = [u["id"] for u in page.json()["items"] + rest.json()["items"]]
    assert len(set(ids)) == 4  # no overlap between pages


@pytest.mark.parametrize("params", [{"limit": 101}, {"limit": 0}, {"offset": -1}])
async def test_list_users_rejects_bad_paging(api_client, admin, params):
    assert (await api_client.get(USERS, params=params, headers=admin[1])).status_code == 422


async def test_get_user_by_id(api_client, admin, employee):
    ok = await api_client.get(f"{USERS}/{employee[0].id}", headers=admin[1])
    missing = await api_client.get(f"{USERS}/{uuid.uuid4()}", headers=admin[1])
    malformed = await api_client.get(f"{USERS}/not-a-uuid", headers=admin[1])

    assert ok.status_code == 200 and ok.json()["email"] == "emp@example.com"
    assert missing.status_code == 404
    assert malformed.status_code == 422


# --- assigning roles -------------------------------------------------------------------


async def test_admin_assigns_role_and_it_applies_immediately(api_client, admin, employee):
    before = await api_client.get(f"{USERS}/me", headers=employee[1])
    assert "customer:update" not in before.json()["permissions"]

    response = await api_client.put(
        f"{USERS}/{employee[0].id}/roles", json={"roles": ["sales"]}, headers=admin[1]
    )

    assert response.status_code == 200
    assert response.json()["roles"] == ["sales"]
    # Same token, no re-login: permissions are read from the DB on every request.
    after = await api_client.get(f"{USERS}/me", headers=employee[1])
    assert "customer:update" in after.json()["permissions"]


async def test_unknown_role_is_rejected(api_client, admin, employee):
    response = await api_client.put(
        f"{USERS}/{employee[0].id}/roles", json={"roles": ["wizard"]}, headers=admin[1]
    )

    assert response.status_code == 400
    assert response.json()["error"]["details"] == {"unknown_roles": ["wizard"]}


async def test_empty_role_list_is_rejected(api_client, admin, employee):
    response = await api_client.put(
        f"{USERS}/{employee[0].id}/roles", json={"roles": []}, headers=admin[1]
    )

    assert response.status_code == 422


async def test_cannot_demote_the_last_admin(api_client, admin):
    response = await api_client.put(
        f"{USERS}/{admin[0].id}/roles", json={"roles": ["manager"]}, headers=admin[1]
    )

    assert response.status_code == 409
    assert "last active admin" in response.json()["error"]["message"]


async def test_can_demote_an_admin_when_another_exists(api_client, session, admin):
    other = await make_user(session, "admin2@example.com", "admin")

    response = await api_client.put(
        f"{USERS}/{other.id}/roles", json={"roles": ["sales"]}, headers=admin[1]
    )

    assert response.status_code == 200


async def test_two_admins_demoting_each_other_concurrently_leave_one_admin(
    session, api_client, test_database_url
):
    """Service level, two independent DB sessions (= two requests), bypassing HTTP.

    Via HTTP the second request is usually stopped by the permission check before it reaches
    the admin count, so the race is never exercised. Here both reach the check-then-act
    section at the same time; only the FOR UPDATE lock on the admin role keeps one admin.
    """
    first = await make_user(session, "admin1@example.com", "admin")
    second = await make_user(session, "admin2@example.com", "admin")
    engine = create_engine(test_database_url)
    factory = create_session_factory(engine)

    async def demote(actor_id: uuid.UUID, target_id: uuid.UUID) -> str:
        async with factory() as db:
            actor = await db.get(User, actor_id)
            try:
                await UserService(db).set_roles(actor, target_id, ["sales"])
                return "ok"
            except ConflictError:
                return "conflict"

    try:
        results = await asyncio.gather(
            demote(first.id, second.id), demote(second.id, first.id)
        )
    finally:
        await engine.dispose()

    assert sorted(results) == ["conflict", "ok"]
    session.expire_all()
    admins = await session.scalar(
        select(func.count()).select_from(User).where(User.roles.any(Role.name == ROLE_ADMIN))
    )
    assert admins == 1


# --- disabling users -------------------------------------------------------------------


async def test_disabling_a_user_revokes_access_immediately(api_client, admin, employee):
    response = await api_client.patch(
        f"{USERS}/{employee[0].id}", json={"is_active": False}, headers=admin[1]
    )

    assert response.status_code == 200 and response.json()["is_active"] is False
    assert (await api_client.get(f"{USERS}/me", headers=employee[1])).status_code == 401


async def test_user_can_be_re_enabled(api_client, admin, employee):
    await api_client.patch(f"{USERS}/{employee[0].id}", json={"is_active": False}, headers=admin[1])

    response = await api_client.patch(
        f"{USERS}/{employee[0].id}", json={"is_active": True}, headers=admin[1]
    )

    assert response.json()["is_active"] is True
    assert (await api_client.get(f"{USERS}/me", headers=employee[1])).status_code == 200


async def test_admin_cannot_disable_themselves(api_client, admin):
    response = await api_client.patch(
        f"{USERS}/{admin[0].id}", json={"is_active": False}, headers=admin[1]
    )

    assert response.status_code == 409


# --- roles and their permissions -------------------------------------------------------


async def test_list_roles_with_permissions(api_client, admin):
    response = await api_client.get(ROLES, headers=admin[1])

    roles = {r["name"]: r for r in response.json()}
    assert set(roles) == {"admin", "manager", "sales", "warehouse", "employee"}
    assert "customer:read" in roles["employee"]["permissions"]
    assert "role:manage" in roles["admin"]["permissions"]


async def test_admin_edits_role_permissions_and_it_applies_immediately(api_client, session, admin, employee):
    employee_role = (await session.execute(select(Role).where(Role.name == "employee"))).scalar_one()

    response = await api_client.put(
        f"{ROLES}/{employee_role.id}/permissions",
        json={"permissions": ["customer:read", "order:read"]},
        headers=admin[1],
    )

    assert response.status_code == 200
    assert response.json()["permissions"] == ["customer:read", "order:read"]
    me = await api_client.get(f"{USERS}/me", headers=employee[1])
    assert me.json()["permissions"] == ["customer:read", "order:read"]


async def test_unknown_permission_code_is_rejected(api_client, session, admin):
    role = (await session.execute(select(Role).where(Role.name == "sales"))).scalar_one()

    response = await api_client.put(
        f"{ROLES}/{role.id}/permissions", json={"permissions": ["nuke:everything"]}, headers=admin[1]
    )

    assert response.status_code == 422


async def test_admin_role_cannot_be_modified(api_client, session, admin):
    role = (await session.execute(select(Role).where(Role.name == "admin"))).scalar_one()

    response = await api_client.put(
        f"{ROLES}/{role.id}/permissions", json={"permissions": []}, headers=admin[1]
    )

    assert response.status_code == 409


async def test_editing_roles_requires_role_manage(api_client, session):
    manager = await make_user(session, "mgr@example.com", "manager")
    role = (await session.execute(select(Role).where(Role.name == "sales"))).scalar_one()

    response = await api_client.put(
        f"{ROLES}/{role.id}/permissions",
        json={"permissions": []},
        headers=await auth_for(api_client, manager),
    )

    assert response.status_code == 403


async def test_editing_a_missing_role_is_404(api_client, admin):
    response = await api_client.put(
        f"{ROLES}/9999/permissions", json={"permissions": []}, headers=admin[1]
    )

    assert response.status_code == 404


# --- admin bootstrap -------------------------------------------------------------------


async def test_ensure_admin_creates_a_working_admin(api_client, session):
    user, created = await ensure_admin(session, "Boss@Example.com", "The Boss", PASSWORD)

    assert created is True and [r.name for r in user.roles] == ["admin"]
    login = await api_client.post(
        "/api/v1/auth/login", json={"email": "boss@example.com", "password": PASSWORD}
    )
    assert login.status_code == 200


async def test_ensure_admin_is_idempotent_and_keeps_the_password(api_client, session):
    first, _ = await ensure_admin(session, "boss@example.com", "Boss", PASSWORD)
    original_hash = first.password_hash

    second, created = await ensure_admin(session, "boss@example.com", "Boss", "another-password")

    assert created is False and second.id == first.id
    assert second.password_hash == original_hash
    assert [r.name for r in second.roles] == ["admin"]  # not duplicated


async def test_ensure_admin_promotes_an_existing_user(session, api_client):
    employee = await make_user(session, "emp@example.com", "employee")

    user, created = await ensure_admin(session, "emp@example.com", "Emp", None)

    assert created is False and user.id == employee.id
    assert {r.name for r in user.roles} == {"employee", "admin"}


async def test_ensure_admin_rejects_a_short_password(session, api_client):
    with pytest.raises(ValueError):
        await ensure_admin(session, "boss@example.com", "Boss", "short")
