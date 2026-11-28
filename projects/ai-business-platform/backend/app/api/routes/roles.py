from fastapi import APIRouter, Depends

from app.api.dependencies import get_role_service, require_permission
from app.core.permissions import PermissionCode
from app.modules.auth.role_service import RoleService
from app.modules.auth.schemas import RoleRead, SetPermissionsRequest
from app.modules.users.models import User

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get(
    "",
    response_model=list[RoleRead],
    dependencies=[Depends(require_permission(PermissionCode.USER_READ))],
)
async def list_roles(service: RoleService = Depends(get_role_service)):
    return [RoleRead.from_role(role) for role in await service.list_roles()]


@router.put("/{role_id}/permissions", response_model=RoleRead)
async def set_role_permissions(
    role_id: int,
    data: SetPermissionsRequest,
    actor: User = Depends(require_permission(PermissionCode.ROLE_MANAGE)),
    service: RoleService = Depends(get_role_service),
):
    role = await service.set_permissions(actor, role_id, [p.value for p in data.permissions])
    return RoleRead.from_role(role)
