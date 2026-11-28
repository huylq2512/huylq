from contextlib import asynccontextmanager


class FakeConnection:
    def __init__(self, fail: bool) -> None:
        self.fail = fail

    async def execute(self, statement):
        if self.fail:
            raise ConnectionRefusedError("db down")


class FakeEngine:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    @asynccontextmanager
    async def connect(self):
        yield FakeConnection(self.fail)


class FakeRedis:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def ping(self):
        if self.fail:
            raise ConnectionRefusedError("redis down")
        return True


def test_ready_when_all_dependencies_ok(app, client):
    app.state.engine = FakeEngine()
    app.state.redis = FakeRedis()

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}


def test_not_ready_when_database_down(app, client):
    app.state.engine = FakeEngine(fail=True)
    app.state.redis = FakeRedis()

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "unavailable", "redis": "ok"}


def test_not_ready_when_redis_down(app, client):
    app.state.engine = FakeEngine()
    app.state.redis = FakeRedis(fail=True)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "ok", "redis": "unavailable"}


def test_liveness_ignores_dependency_failures(app, client):
    app.state.engine = FakeEngine(fail=True)
    app.state.redis = FakeRedis(fail=True)

    assert client.get("/health").status_code == 200
