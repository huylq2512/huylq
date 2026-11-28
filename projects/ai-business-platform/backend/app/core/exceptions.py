"""Domain exceptions and their mapping to a uniform HTTP error body.

Every error response has the same shape:
    {"error": {"code": "...", "message": "...", "request_id": "...", "details": ...}}
Services raise AppError subclasses; they carry a status code but no HTTP objects.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 500
    code = "internal_error"
    headers: dict[str, str] | None = None  # extra response headers (e.g. WWW-Authenticate)

    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    headers = {"WWW-Authenticate": "Bearer"}


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ServiceUnavailableError(AppError):
    """A required dependency (Redis, an external API...) is down."""

    status_code = 503
    code = "service_unavailable"


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = {
        "error": {
            "code": code,
            "message": message,
            # read from request.state: robust even if the ContextVar was already reset
            "request_id": getattr(request.state, "request_id", None),
            "details": details,
        }
    }
    return JSONResponse(status_code=status_code, content=body, headers=headers)


async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return _error_response(
        request, exc.status_code, exc.code, exc.message, exc.details, exc.headers
    )


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Keep only loc/msg/type: pydantic's raw error dicts can hold non-serializable objects.
    details = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return _error_response(request, 422, "validation_error", "Request validation failed", details)


async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = "not_found" if exc.status_code == 404 else "http_error"
    return _error_response(request, exc.status_code, code, str(exc.detail))


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    # Full traceback goes to the log; the client only gets a generic message (no leaks).
    logger.exception("unhandled_exception", extra={"path": request.url.path})
    return _error_response(request, 500, "internal_error", "Internal server error")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected)
