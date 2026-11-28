"""Password hashing (Argon2id) and JWT access tokens.

Pure functions with no framework or database dependency, so they are trivial to unit test.
Hashing is CPU-heavy by design: call it through `asyncio.to_thread` from async code so it
does not block the event loop.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.exceptions import UnauthorizedError

# argon2-cffi defaults follow the RFC 9106 low-memory recommendation. The hash string embeds
# the parameters and salt, so parameters can be raised later without breaking old hashes.
_password_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except (VerificationError, InvalidHashError):
        # VerifyMismatchError is a VerificationError; a corrupt stored hash is also "no".
        return False


# Verified against when the email is unknown, so "no such user" and "wrong password" take
# about the same time (prevents user enumeration through response timing).
DUMMY_PASSWORD_HASH = hash_password("timing-equalisation-dummy")


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    jti: str  # unique token id: what the logout denylist stores
    expires_at: datetime


def create_access_token(
    user_id: uuid.UUID,
    *,
    secret_key: str,
    algorithm: str,
    expires_minutes: int,
    now: datetime | None = None,
) -> tuple[str, TokenClaims]:
    issued_at = now or datetime.now(UTC)
    claims = TokenClaims(
        user_id=user_id,
        jti=uuid.uuid4().hex,
        expires_at=issued_at + timedelta(minutes=expires_minutes),
    )
    payload = {
        "sub": str(claims.user_id),
        "jti": claims.jti,
        "iat": issued_at,
        "exp": claims.expires_at,
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm), claims


def decode_access_token(token: str, *, secret_key: str, algorithm: str) -> TokenClaims:
    """Validate signature and expiry. Raises UnauthorizedError for any problem."""
    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],  # fixed list: blocks "alg: none" and key-confusion tricks
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
        return TokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            jti=payload["jti"],
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token has expired") from None
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise UnauthorizedError("Invalid token") from None
