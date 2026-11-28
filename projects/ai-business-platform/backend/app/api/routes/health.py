import asyncio
import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.dependencies import get_app_settings
from app.config import Settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health(settings: Settings = Depends(get_app_settings)) -> dict[str, str]:
    """Liveness: the process is up. Never touches dependencies."""
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


async def _check(name: str, probe: Callable[[], Awaitable[object]], timeout: float) -> str:
    try:
        await asyncio.wait_for(probe(), timeout=timeout)
        return "ok"
    except Exception:  # any failure means "not ready"; details go to the log, not the client
        logger.warning("readiness_check_failed", extra={"check": name}, exc_info=True)
        return "unavailable"


@router.get("/health/ready")
async def readiness(
    request: Request, settings: Settings = Depends(get_app_settings)
) -> JSONResponse:
    """Readiness: the app can serve traffic (database and Redis reachable)."""
    state = request.app.state
    timeout = settings.health_check_timeout_seconds

    async def probe_database() -> None:
        async with state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    checks = {
        "database": await _check("database", probe_database, timeout),
        "redis": await _check("redis", state.redis.ping, timeout),
    }
    ready = all(value == "ok" for value in checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ok" if ready else "unavailable", "checks": checks},
    )
