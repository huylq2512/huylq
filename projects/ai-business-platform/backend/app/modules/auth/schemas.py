from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from app.core.permissions import PermissionCode
from app.modules.auth.models import Role

# Upper bound on password length: hashing cost grows with input, so unbounded input is a DoS
# vector. 128 is far beyond any real password or passphrase.
Password = Annotated[str, Field(min_length=8, max_length=128)]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Password
    full_name: FullName


class LoginRequest(BaseModel):
    email: EmailStr
    # No min_length here: do not reveal the password policy to someone guessing.
    password: str = Field(min_length=1, max_length=128)


class RoleRead(BaseModel):
    id: int
    name: str
    description: str | None
    permissions: list[str]

    @classmethod
    def from_role(cls, role: Role) -> "RoleRead":
        return cls(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=sorted(p.code for p in role.permissions),
        )


class SetPermissionsRequest(BaseModel):
    # Full replacement. Typed with the enum so unknown codes are rejected with 422.
    permissions: list[PermissionCode] = Field(max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
