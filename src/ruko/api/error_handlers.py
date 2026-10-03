"""Exception handlers that turn every failure into the standard error contract."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ruko.errors import ERROR_SPECS, ErrorCode, RukoError, build_error_response
from ruko.observability import log_event

_STATUS_TO_CODE: dict[int, ErrorCode] = {
    400: ErrorCode.INVALID_REQUEST,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    413: ErrorCode.PAYLOAD_TOO_LARGE,
    415: ErrorCode.UNSUPPORTED_MEDIA_TYPE,
    422: ErrorCode.INVALID_REQUEST,
    429: ErrorCode.RATE_LIMITED,
}


def error_json(code: ErrorCode, fields: list[str] | None = None) -> JSONResponse:
    """Build a JSON error response for a code, with its HTTP status."""
    body = build_error_response(code, fields).model_dump(mode="json", exclude_none=True)
    return JSONResponse(status_code=ERROR_SPECS[code].http_status, content=body)


async def _handle_ruko_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RukoError)
    log_event("request_failed", logging.WARNING, error_code=exc.code.value)
    return error_json(exc.code)


async def _handle_validation_error(_request: Request, exc: Exception) -> JSONResponse:
    # Only field locations are returned. FastAPI's default handler echoes the
    # submitted input, which could contain message text; we never do that.
    assert isinstance(exc, RequestValidationError)
    locations = sorted({".".join(str(part) for part in err.get("loc", ())) for err in exc.errors()})
    log_event("request_failed", logging.INFO, error_code=ErrorCode.INVALID_REQUEST.value)
    return error_json(ErrorCode.INVALID_REQUEST, fields=locations)


async def _handle_http_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _STATUS_TO_CODE.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    return error_json(code)


async def _handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
    # Exception messages can contain input data, so only the type name is logged.
    log_event(
        "unhandled_exception",
        logging.ERROR,
        error_code=ErrorCode.INTERNAL_ERROR.value,
        exception_type=type(exc).__name__,
    )
    return error_json(ErrorCode.INTERNAL_ERROR)


def install_error_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the app."""
    app.add_exception_handler(RukoError, _handle_ruko_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(Exception, _handle_unexpected)
