import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.permissions import ROLE_ADMIN
from app.modules.auth.models import Role
from app.modules.auth.repository import RoleRepository
from app.modules.users.models import User

logger = logging.getLogger(__name__)


class RoleService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._roles = RoleRepository(session)

    async def list_roles(self) -> list[Role]:
        return await self._roles.list_all()

    async def set_permissions(self, actor: User, role_id: int, codes: list[str]) -> Role:
        role = await self._roles.get_by_id(role_id)
        if role is None:
            raise NotFoundError("Role not found")
        if role.name == ROLE_ADMIN:
            # Admin must always hold everything; editing it could lock everybody out.
            raise ConflictError("The admin role cannot be modified")

        wanted = set(codes)
        permissions = await self._roles.get_permissions_by_codes(wanted)
        unknown = wanted - {p.code for p in permissions}
        if unknown:
            raise BadRequestError(
                "Unknown permission(s)", details={"unknown_permissions": sorted(unknown)}
            )

        role.permissions = permissions
        await self._session.commit()
        logger.info(
            "role_permissions_changed",
            extra={"actor_id": str(actor.id), "role": role.name, "permissions": sorted(wanted)},
        )
        return role
