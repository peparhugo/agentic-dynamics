"""Consistent JSON error handling.

All errors are returned in a single envelope:

    {"error": {"code": <int>, "type": <str>, "message": <str>, "details": <obj|null>}}
"""
from flask import Flask, jsonify
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    """Raise anywhere in a view to return a structured error response."""

    def __init__(self, message: str, status_code: int = 400, error_type: str | None = None, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type or _default_type(status_code)
        self.details = details


def _default_type(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "validation_error",
        429: "rate_limit_exceeded",
        500: "internal_error",
    }.get(status_code, "error")


def error_response(status_code: int, message: str, error_type: str | None = None, details=None):
    payload = {
        "error": {
            "code": status_code,
            "type": error_type or _default_type(status_code),
            "message": message,
            "details": details,
        }
    }
    return jsonify(payload), status_code


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(APIError)
    def handle_api_error(err: APIError):
        return error_response(err.status_code, err.message, err.error_type, err.details)

    @app.errorhandler(ValidationError)
    def handle_validation_error(err: ValidationError):
        return error_response(422, "Input validation failed.", "validation_error", err.messages)

    @app.errorhandler(429)
    def handle_rate_limit(err):
        return error_response(429, f"Rate limit exceeded: {err.description}.", "rate_limit_exceeded")

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        return error_response(err.code or 500, err.description or err.name)

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):  # pragma: no cover - safety net
        app.logger.exception("Unhandled exception")
        return error_response(500, "An unexpected error occurred.")
