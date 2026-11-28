"""Fixtures for DB integration tests.

They run against a dedicated throw-away database (`<name>_test`) created from scratch with
the real Alembic migrations, so the development database is never touched and the migration
chain itself is exercised on every run.
"""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

from urllib.parse import urlparse

import asyncpg
import httpx
import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.main import create_app
from app.modules.auth.seed import seed_rbac

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def test_database_url() -> str:
    dev_url = make_url(get_settings().database_url)
    test_db = f"{dev_url.database}_test"

    async def recreate() -> None:
        # Connect to the maintenance DB ("postgres") to drop/create the test database.
        conn = await asyncpg.connect(
            user=dev_url.username,
            password=dev_url.password,
            host=dev_url.host,
            port=dev_url.port,
            database="postgres",
        )
        try:
            await conn.execute(f'DROP DATABASE IF EXISTS "{test_db}" WITH (FORCE)')
            await conn.execute(f'CREATE DATABASE "{test_db}"')
        finally:
            await conn.close()

    asyncio.run(recreate())

    url = dev_url.set(database=test_db).render_as_string(hide_password=False)
    # Real migrations, in a subprocess: env vars override .env, so Alembic targets the test DB.
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": url},
        check=True,
        capture_output=True,
    )
    return url


@pytest.fixture(scope="session")
def test_redis_url() -> str:
    """Redis logical DB 15, flushed at session start, so tests never touch app data in DB 0."""
    url = urlparse(get_settings().redis_url)._replace(path="/15").geturl()

    async def flush() -> None:
        client = Redis.from_url(url)
        try:
            await client.flushdb()
        finally:
            await client.aclose()

    asyncio.run(flush())
    return url


@pytest_asyncio.fixture
async def api_client(
    session: AsyncSession, test_database_url: str, test_redis_url: str
) -> AsyncIterator[httpx.AsyncClient]:
    """The real app (real lifespan, test DB, Redis DB 15) driven over ASGI, RBAC seeded."""
    await seed_rbac(session)
    app = create_app(
        get_settings().model_copy(
            update={"database_url": test_database_url, "redis_url": test_redis_url}
        )
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            client.app = app  # exposed for tests that need app.state / settings
            yield client


@pytest_asyncio.fixture
async def session(test_database_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_engine(test_database_url)
    try:
        async with create_session_factory(engine)() as db_session:
            yield db_session
        # Reset data between tests (schema stays). CASCADE also clears the link tables.
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE users, roles, permissions RESTART IDENTITY CASCADE"))
    finally:
        await engine.dispose()
