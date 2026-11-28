import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.permissions import PermissionCode
from app.core.security import TokenClaims, decode_access_token
from app.modules.auth.denylist import TokenDenylist
from app.modules.auth.role_service import RoleService
from app.modules.auth.service import AuthService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService

logger = logging.getLogger(__name__)

# auto_error=False: a missing header must produce OUR uniform 401 body, not FastAPI's default.
bearer_scheme = HTTPBearer(auto_error=False)


def get_app_settings(request: Request) -> Settings:
    """Settings of the running app (set in create_app), so tests can override them."""
    return request.app.state.settings


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One AsyncSession per request.

    The session is NOT committed automatically: services decide where the transaction
    boundary is and call `await session.commit()` explicitly. If an exception escapes,
    closing the session rolls back anything uncommitted.
    """
    async with request.app.state.session_factory() as session:
        yield session


def get_auth_service(
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_app_settings),
) -> AuthService:
    return AuthService(session, TokenDenylist(redis), settings)


async def get_current_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_app_settings),
    redis: Redis = Depends(get_redis),
) -> TokenClaims:
    """Authenticate the request: valid signature, not expired, not revoked."""
    if credentials is None:
        raise UnauthorizedError("Not authenticated")
    claims = decode_access_token(
        credentials.credentials, secret_key=settings.secret_key, algorithm=settings.jwt_algorithm
    )
    if await TokenDenylist(redis).is_revoked(claims.jti):
        raise UnauthorizedError("Token has been revoked")
    return claims


async def get_current_user(
    claims: TokenClaims = Depends(get_current_claims),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Load the user on every request so that disabling an account takes effect at once."""
    user = await UserRepository(session).get_by_id(claims.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid token")
    return user


def require_permission(*required: PermissionCode) -> Callable[..., Awaitable[User]]:
    """Dependency factory: 401 if not authenticated, 403 unless the user holds ALL of `required`.

    Usage:  current_user: User = Depends(require_permission(PermissionCode.USER_MANAGE))
    Permissions are read from the database on every request (via get_current_user), so
    role changes apply immediately, not at the next login.
    """

    async def checker(user: User = Depends(get_current_user)) -> User:
        missing = [code.value for code in required if code.value not in user.permission_codes]
        if missing:
            # Log what was missing; tell the client only that access is denied.
            logger.warning(
                "permission_denied", extra={"user_id": str(user.id), "missing": missing}
            )
            raise ForbiddenError("You do not have permission to perform this action")
        return user

    return checker


def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    return UserService(session)


def get_role_service(session: AsyncSession = Depends(get_session)) -> RoleService:
    return RoleService(session)
