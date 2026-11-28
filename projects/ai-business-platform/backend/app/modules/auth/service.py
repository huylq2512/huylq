import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import AppError, ConflictError, UnauthorizedError
from app.core.permissions import ROLE_EMPLOYEE
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    TokenClaims,
    create_access_token,
    hash_password,
    verify_password,
)
from app.modules.auth.denylist import TokenDenylist
from app.modules.auth.repository import RoleRepository
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS = "Invalid email or password"


class AuthService:
    def __init__(self, session: AsyncSession, denylist: TokenDenylist, settings: Settings) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._roles = RoleRepository(session)
        self._denylist = denylist
        self._settings = settings

    async def register(self, data: RegisterRequest) -> User:
        """Self-registration. New accounts get the least-privileged role only."""
        email = data.email.strip().lower()
        if await self._users.get_by_email(email):
            raise ConflictError("Email is already registered")

        role = await self._roles.get_by_name(ROLE_EMPLOYEE)
        if role is None:
            logger.error("default_role_missing", extra={"role": ROLE_EMPLOYEE})
            raise AppError("Server is not configured: run the RBAC seed")

        # Argon2 is deliberately slow and CPU-bound: keep it off the event loop.
        password_hash = await asyncio.to_thread(hash_password, data.password)
        user = User(email=email, password_hash=password_hash, full_name=data.full_name)
        user.roles.append(role)
        self._users.add(user)
        try:
            await self._session.commit()
        except IntegrityError:
            # Two concurrent registrations passed the check above; the unique index decides.
            await self._session.rollback()
            raise ConflictError("Email is already registered") from None
        return user

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self._users.get_by_email(data.email.strip())

        # Always run one hash verification (against a dummy if the user is unknown) so the
        # response time does not reveal whether the email exists.
        stored_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
        password_ok = await asyncio.to_thread(verify_password, data.password, stored_hash)

        if user is None or not password_ok or not user.is_active:
            # One message for every failure: no hint about which part was wrong.
            raise UnauthorizedError(INVALID_CREDENTIALS)

        user.last_login_at = datetime.now(UTC)
        await self._session.commit()

        token, claims = create_access_token(
            user.id,
            secret_key=self._settings.secret_key,
            algorithm=self._settings.jwt_algorithm,
            expires_minutes=self._settings.access_token_expire_minutes,
        )
        logger.info("user_logged_in", extra={"user_id": str(user.id), "jti": claims.jti})
        return TokenResponse(
            access_token=token, expires_in=self._settings.access_token_expire_minutes * 60
        )

    async def logout(self, claims: TokenClaims) -> None:
        remaining = int((claims.expires_at - datetime.now(UTC)).total_seconds())
        await self._denylist.revoke(claims.jti, remaining)
        logger.info("user_logged_out", extra={"user_id": str(claims.user_id), "jti": claims.jti})
