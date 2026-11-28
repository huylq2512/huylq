"""Revoked-token list (for logout), stored in Redis.

JWTs are stateless, so "logout" needs server-side state: we remember the `jti` of revoked
tokens until they would have expired anyway (TTL), after which the entry is useless and
Redis drops it. Memory use is therefore bounded by (logouts per token lifetime).

Fail-closed: if Redis is unreachable we cannot prove a token is not revoked, so callers get
503 instead of silently accepting possibly revoked tokens.
"""

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.exceptions import ServiceUnavailableError

_KEY_PREFIX = "jwt:denylist:"


class TokenDenylist:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        try:
            await self._redis.set(_KEY_PREFIX + jti, "1", ex=max(1, ttl_seconds))
        except RedisError:
            raise ServiceUnavailableError("Authentication service temporarily unavailable") from None

    async def is_revoked(self, jti: str) -> bool:
        try:
            return bool(await self._redis.exists(_KEY_PREFIX + jti))
        except RedisError:
            raise ServiceUnavailableError("Authentication service temporarily unavailable") from None
