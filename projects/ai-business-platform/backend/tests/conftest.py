import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings():
    # Explicit values so unit tests never depend on a local .env. Port 1 = nothing listens.
    return Settings(
        app_env="test",
        database_url="postgresql+asyncpg://user:pass@localhost:1/db",
        redis_url="redis://localhost:1/0",
        secret_key="unit-test-secret-key-at-least-32-characters",
        health_check_timeout_seconds=0.5,
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    # No `with`: the lifespan (engine/redis creation) is not run for unit tests.
    # raise_server_exceptions=False so unhandled errors become HTTP 500 like for real clients.
    return TestClient(app, raise_server_exceptions=False)
