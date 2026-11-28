import uuid

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user, get_user_service, require_permission
from app.core.permissions import PermissionCode
from app.modules.users.models import User
from app.modules.users.schemas import SetRolesRequest, UpdateUserRequest, UserList, UserRead
from app.modules.users.service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_me(current_user: User = Depends(get_current_user)):
    return UserRead.from_user(current_user)


@router.get(
    "", response_model=UserList, dependencies=[Depends(require_permission(PermissionCode.USER_READ))]
)
async def list_users(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: UserService = Depends(get_user_service),
):
    users, total = await service.list_users(limit, offset)
    return UserList(
        items=[UserRead.from_user(u) for u in users], total=total, limit=limit, offset=offset
    )


@router.get(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(require_permission(PermissionCode.USER_READ))],
)
async def read_user(user_id: uuid.UUID, service: UserService = Depends(get_user_service)):
    return UserRead.from_user(await service.get_user(user_id))


@router.put("/{user_id}/roles", response_model=UserRead)
async def set_user_roles(
    user_id: uuid.UUID,
    data: SetRolesRequest,
    actor: User = Depends(require_permission(PermissionCode.USER_MANAGE)),
    service: UserService = Depends(get_user_service),
):
    return UserRead.from_user(await service.set_roles(actor, user_id, data.roles))


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    data: UpdateUserRequest,
    actor: User = Depends(require_permission(PermissionCode.USER_MANAGE)),
    service: UserService = Depends(get_user_service),
):
    return UserRead.from_user(await service.set_active(actor, user_id, data.is_active))
