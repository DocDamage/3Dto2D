from __future__ import annotations

import logging
from typing import Any

from flask import jsonify

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Expected API failure with a client-safe message."""

    def __init__(self, message: str, status: int = 400, *, code: str = "bad_request") -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def json_error(message: str, status: int = 400, *, code: str = "error"):
    return jsonify({"ok": False, "message": message, "code": code}), status


def api_exception_response(exc: Exception, *, default_status: int = 500, context: str = "api"):
    if isinstance(exc, ApiError):
        return json_error(exc.message, exc.status, code=exc.code)
    if isinstance(exc, FileNotFoundError):
        return json_error(str(exc) or "File not found", 404, code="not_found")
    if isinstance(exc, ValueError):
        return json_error(str(exc) or "Invalid request", default_status if default_status < 500 else 400, code="invalid_request")
    if isinstance(exc, RuntimeError) and default_status < 500:
        return json_error(str(exc) or "Request failed", default_status, code="request_failed")

    logger.exception("Unhandled %s error", context, exc_info=exc)
    return json_error("Internal server error", default_status, code="internal_error")


def ok_json(payload: dict[str, Any] | None = None, **extra: Any):
    data = {"ok": True}
    if payload:
        data.update(payload)
    data.update(extra)
    return jsonify(data)
