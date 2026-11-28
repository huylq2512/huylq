import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Role
from app.modules.users.models import User, user_roles


class UserRepository:
    """Queries only. Transactions (commit/rollback) are owned by the service layer."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        # Matches the unique index on lower(email), so this lookup is index-backed.
        stmt = select(User).where(func.lower(User.email) == email.lower())
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_page(self, limit: int, offset: int) -> tuple[list[User], int]:
        total = await self._session.scalar(select(func.count()).select_from(User))
        stmt = (
            select(User)
            .order_by(User.created_at.desc(), User.id)  # id breaks ties: stable pagination
            .limit(limit)
            .offset(offset)
        )
        return list((await self._session.execute(stmt)).scalars()), total or 0

    async def count_active_with_role(self, role_name: str) -> int:
        stmt = (
            select(func.count(func.distinct(User.id)))
            .select_from(User)
            .join(user_roles, user_roles.c.user_id == User.id)
            .join(Role, Role.id == user_roles.c.role_id)
            .where(Role.name == role_name, User.is_active.is_(True))
        )
        return await self._session.scalar(stmt) or 0

    def add(self, user: User) -> None:
        self._session.add(user)
