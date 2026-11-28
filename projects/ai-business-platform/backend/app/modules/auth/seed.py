"""Idempotent seed of roles, permissions and the default role -> permission matrix.

Run:  python -m app.modules.auth.seed

Safe to run any number of times (deploys, tests): it only inserts what is missing and never
deletes or rewrites rows. Permissions an admin ADDED to a role are therefore kept; a default
permission an admin REMOVED from a role comes back on the next seed (the matrix in
core/permissions.py is the baseline).
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.logging import setup_logging
from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, ROLE_DESCRIPTIONS, PermissionCode
from app.modules.auth.models import Permission, Role, role_permissions

logger = logging.getLogger(__name__)


async def seed_rbac(session: AsyncSession) -> dict[str, int]:
    """Insert missing permissions, roles and links. Commits. Returns how many rows were added."""
    added = {"permissions": 0, "roles": 0, "role_permissions": 0}

    # ON CONFLICT DO NOTHING + RETURNING: only rows actually inserted come back, and it is
    # race-safe if two deploys seed at the same time (unlike "SELECT then INSERT").
    result = await session.execute(
        insert(Permission)
        .values([{"code": code.value} for code in PermissionCode])
        .on_conflict_do_nothing(index_elements=["code"])
        .returning(Permission.id)
    )
    added["permissions"] = len(result.all())

    result = await session.execute(
        insert(Role)
        .values([{"name": n, "description": d} for n, d in ROLE_DESCRIPTIONS.items()])
        .on_conflict_do_nothing(index_elements=["name"])
        .returning(Role.id)
    )
    added["roles"] = len(result.all())

    role_ids = dict((await session.execute(select(Role.name, Role.id))).all())
    permission_ids = dict((await session.execute(select(Permission.code, Permission.id))).all())

    links = [
        {"role_id": role_ids[role], "permission_id": permission_ids[code.value]}
        for role, codes in DEFAULT_ROLE_PERMISSIONS.items()
        for code in codes
    ]
    result = await session.execute(
        insert(role_permissions)
        .values(links)
        .on_conflict_do_nothing()  # composite PK (role_id, permission_id)
        .returning(role_permissions.c.role_id)
    )
    added["role_permissions"] = len(result.all())

    await session.commit()
    return added


async def _main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    engine = create_engine(settings.database_url)
    try:
        async with create_session_factory(engine)() as session:
            added = await seed_rbac(session)
        logger.info("rbac_seeded", extra={"added": added})
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
