"""Integration tests: need `docker compose up -d db redis` and `alembic upgrade head`.

Run with:  pytest -m integration
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def live_client():
    # `with` runs the lifespan, creating the real engine and Redis client from .env.
    with TestClient(create_app(get_settings())) as client:
        yield client


def test_readiness_against_real_database_and_redis(live_client):
    response = live_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "redis": "ok"}


def test_pgvector_extension_is_installed(live_client):
    import asyncio

    async def query() -> str | None:
        engine = live_client.app.state.engine
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
            return result.scalar_one_or_none()

    assert asyncio.run(query()) == "vector"
