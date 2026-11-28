import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.core.permissions import (
    DEFAULT_ROLE_PERMISSIONS,
    ROLE_ADMIN,
    ROLE_EMPLOYEE,
    ROLE_MANAGER,
    PermissionCode,
)
from app.modules.auth.models import Permission, Role, role_permissions
from app.modules.auth.seed import seed_rbac
from app.modules.users.models import User, user_roles

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _role(session, name: str) -> Role:
    return (await session.execute(select(Role).where(Role.name == name))).scalar_one()


def _user(email: str = "a@example.com") -> User:
    return User(email=email, password_hash="x", full_name="Test User")


async def test_seed_inserts_everything_on_empty_database(session):
    added = await seed_rbac(session)

    assert added == {
        "permissions": len(PermissionCode),
        "roles": 5,
        "role_permissions": sum(len(codes) for codes in DEFAULT_ROLE_PERMISSIONS.values()),
    }


async def test_seed_is_idempotent(session):
    await seed_rbac(session)

    second = await seed_rbac(session)

    assert second == {"permissions": 0, "roles": 0, "role_permissions": 0}
    assert await session.scalar(select(func.count()).select_from(Role)) == 5


async def test_default_matrix_is_applied(session):
    await seed_rbac(session)

    admin = {p.code for p in (await _role(session, ROLE_ADMIN)).permissions}
    manager = {p.code for p in (await _role(session, ROLE_MANAGER)).permissions}
    employee = {p.code for p in (await _role(session, ROLE_EMPLOYEE)).permissions}

    assert admin == {c.value for c in PermissionCode}
    assert PermissionCode.ROLE_MANAGE not in manager
    assert PermissionCode.CUSTOMER_UPDATE in manager
    assert PermissionCode.CUSTOMER_UPDATE not in employee
    assert PermissionCode.CUSTOMER_READ in employee


async def test_reseed_keeps_permissions_added_at_runtime(session):
    await seed_rbac(session)
    employee = await _role(session, ROLE_EMPLOYEE)
    extra = (
        await session.execute(select(Permission).where(Permission.code == PermissionCode.ORDER_READ))
    ).scalar_one()
    employee.permissions.append(extra)
    await session.commit()

    await seed_rbac(session)

    session.expire_all()
    codes = {p.code for p in (await _role(session, ROLE_EMPLOYEE)).permissions}
    assert PermissionCode.ORDER_READ in codes


async def test_email_is_unique_case_insensitively(session):
    session.add(_user("Alice@Example.com"))
    await session.commit()

    session.add(_user("alice@example.com"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_empty_email_is_rejected(session):
    session.add(_user(""))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_new_user_gets_defaults_and_timestamps(session):
    user = _user()
    session.add(user)
    await session.commit()
    await session.refresh(user)

    assert user.id is not None
    assert user.is_active is True
    assert user.created_at is not None and user.updated_at is not None
    assert user.last_login_at is None


async def test_user_roles_are_loaded_and_cascade_on_user_delete(session):
    await seed_rbac(session)
    user = _user()
    user.roles.append(await _role(session, ROLE_EMPLOYEE))
    session.add(user)
    await session.commit()
    assert await session.scalar(select(func.count()).select_from(user_roles)) == 1

    await session.delete(user)
    await session.commit()

    assert await session.scalar(select(func.count()).select_from(user_roles)) == 0
    assert await session.scalar(select(func.count()).select_from(Role)) == 5  # roles untouched


async def test_cannot_delete_a_role_that_is_still_assigned(session):
    await seed_rbac(session)
    user = _user()
    user.roles.append(await _role(session, ROLE_EMPLOYEE))
    session.add(user)
    await session.commit()

    # Raw SQL: bypasses the ORM so the *database* constraint (RESTRICT) is what is tested.
    with pytest.raises(IntegrityError):
        await session.execute(text("DELETE FROM roles WHERE name = 'employee'"))


async def test_deleting_a_role_removes_its_permission_links(session):
    await seed_rbac(session)
    await session.execute(text("DELETE FROM roles WHERE name = 'sales'"))
    await session.commit()

    remaining = await session.scalar(select(func.count()).select_from(role_permissions))
    expected = sum(
        len(codes) for role, codes in DEFAULT_ROLE_PERMISSIONS.items() if role != "sales"
    )
    assert remaining == expected
