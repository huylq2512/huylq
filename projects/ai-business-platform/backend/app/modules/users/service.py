import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.permissions import ROLE_ADMIN
from app.modules.auth.repository import RoleRepository
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

logger = logging.getLogger(__name__)


class UserService:
    """Administration of existing users. Callers must already have checked permissions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._roles = RoleRepository(session)

    async def list_users(self, limit: int, offset: int) -> tuple[list[User], int]:
        return await self._users.list_page(limit, offset)

    async def get_user(self, user_id: uuid.UUID) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def set_roles(self, actor: User, user_id: uuid.UUID, role_names: list[str]) -> User:
        # Lock first: everything below (count admins, then change) must not interleave with
        # another transaction doing the same, or two admins could demote each other at once.
        await self._roles.lock_by_name(ROLE_ADMIN)
        user = await self.get_user(user_id)

        wanted = set(role_names)
        roles = await self._roles.get_by_names(wanted)
        unknown = wanted - {role.name for role in roles}
        if unknown:
            raise BadRequestError("Unknown role(s)", details={"unknown_roles": sorted(unknown)})

        loses_admin = user.is_active and ROLE_ADMIN not in wanted and self._is_admin(user)
        if loses_admin:
            await self._ensure_another_active_admin()

        user.roles = roles
        await self._session.commit()
        logger.info(
            "user_roles_changed",
            extra={"actor_id": str(actor.id), "user_id": str(user.id), "roles": sorted(wanted)},
        )
        return user

    async def set_active(self, actor: User, user_id: uuid.UUID, is_active: bool) -> User:
        await self._roles.lock_by_name(ROLE_ADMIN)
        user = await self.get_user(user_id)

        if not is_active:
            if user.id == actor.id:
                raise ConflictError("You cannot disable your own account")
            if user.is_active and self._is_admin(user):
                await self._ensure_another_active_admin()

        user.is_active = is_active
        await self._session.commit()
        logger.info(
            "user_active_changed",
            extra={"actor_id": str(actor.id), "user_id": str(user.id), "is_active": is_active},
        )
        return user

    @staticmethod
    def _is_admin(user: User) -> bool:
        return any(role.name == ROLE_ADMIN for role in user.roles)

    async def _ensure_another_active_admin(self) -> None:
        """Call before removing an active admin: at least one other must remain."""
        if await self._users.count_active_with_role(ROLE_ADMIN) <= 1:
            raise ConflictError("Cannot remove or disable the last active admin")
