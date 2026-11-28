from app.core.exceptions import ConflictError, NotFoundError


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "AI Business Management Platform",
        "env": "test",
    }


def test_response_has_generated_request_id(client):
    response = client.get("/health")
    assert len(response.headers["X-Request-ID"]) == 32


def test_incoming_request_id_is_echoed(client):
    response = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert response.headers["X-Request-ID"] == "abc-123"


def test_unknown_route_uses_uniform_error_body(client):
    response = client.get("/nope", headers={"X-Request-ID": "rid-1"})
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "request_id": "rid-1",
            "details": None,
        }
    }


def test_app_error_maps_to_status_and_code(app, client):
    @app.get("/_t/conflict")
    async def conflict():
        raise ConflictError("SKU already exists", details={"sku": "X1"})

    response = client.get("/_t/conflict")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "conflict"
    assert error["message"] == "SKU already exists"
    assert error["details"] == {"sku": "X1"}


def test_not_found_error(app, client):
    @app.get("/_t/missing")
    async def missing():
        raise NotFoundError("Customer not found")

    response = client.get("/_t/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_validation_error_is_422_with_details(app, client):
    @app.get("/_t/items/{item_id}")
    async def item(item_id: int):
        return {"id": item_id}

    response = client.get("/_t/items/not-a-number")
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["loc"] == ["path", "item_id"]


def test_unhandled_exception_hides_internals(app, client):
    @app.get("/_t/boom")
    async def boom():
        raise RuntimeError("secret internal detail")

    response = client.get("/_t/boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret" not in response.text
