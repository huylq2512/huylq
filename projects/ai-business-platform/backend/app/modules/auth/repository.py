from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Permission, Role


class RoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, role_id: int) -> Role | None:
        return await self._session.get(Role, role_id)

    async def get_by_name(self, name: str) -> Role | None:
        return (
            await self._session.execute(select(Role).where(Role.name == name))
        ).scalar_one_or_none()

    async def list_all(self) -> list[Role]:
        return list((await self._session.execute(select(Role).order_by(Role.name))).scalars())

    async def get_by_names(self, names: Collection[str]) -> list[Role]:
        stmt = select(Role).where(Role.name.in_(names))
        return list((await self._session.execute(stmt)).scalars())

    async def lock_by_name(self, name: str) -> Role | None:
        """SELECT ... FOR UPDATE: concurrent transactions queue here until we commit.

        Used to serialise operations that could remove the last admin (check-then-act).
        """
        stmt = select(Role).where(Role.name == name).with_for_update()
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_permissions_by_codes(self, codes: Collection[str]) -> list[Permission]:
        stmt = select(Permission).where(Permission.code.in_(codes))
        return list((await self._session.execute(stmt)).scalars())
