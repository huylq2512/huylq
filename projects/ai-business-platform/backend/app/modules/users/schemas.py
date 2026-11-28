import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.users.models import User


class UserRead(BaseModel):
    """Public view of a user. Never includes password_hash."""

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    roles: list[str]
    permissions: list[str]
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserRead":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            roles=[role.name for role in user.roles],
            permissions=sorted(user.permission_codes),
            created_at=user.created_at,
        )


class UserList(BaseModel):
    items: list[UserRead]
    total: int
    limit: int
    offset: int


class SetRolesRequest(BaseModel):
    # Full replacement of the user's roles. At least one: a user always has some role.
    roles: list[str] = Field(min_length=1, max_length=20)


class UpdateUserRequest(BaseModel):
    is_active: bool
