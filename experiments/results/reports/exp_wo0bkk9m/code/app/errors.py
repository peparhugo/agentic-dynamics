"""Centralized error handling: consistent JSON error envelope for everything."""
from flask import jsonify
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    """Application-level error with a stable machine-readable code."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, status_code: int | None = None,
                 code: str | None = None, details=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.details = details


class NotFoundError(APIError):
    status_code = 404
    code = "not_found"


class UnauthorizedError(APIError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(APIError):
    status_code = 403
    code = "forbidden"


class ConflictError(APIError):
    status_code = 409
    code = "conflict"


def error_response(status_code: int, code: str, message: str, details=None):
    payload = {"error": {"code": code, "message": message}}
    if details:
        payload["error"]["details"] = details
    response = jsonify(payload)
    response.status_code = status_code
    return response


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(err: APIError):
        return error_response(err.status_code, err.code, err.message, err.details)

    @app.errorhandler(ValidationError)
    def handle_validation_error(err: ValidationError):
        return error_response(422, "validation_error", "Input validation failed.",
                              details=err.messages)

    @app.errorhandler(429)
    def handle_rate_limit(err):
        return error_response(
            429, "rate_limit_exceeded",
            f"Rate limit exceeded: {err.description}.",
        )

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        code_map = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
            415: "unsupported_media_type",
        }
        return error_response(
            err.code or 500,
            code_map.get(err.code, "http_error"),
            err.description or "An HTTP error occurred.",
        )

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):  # pragma: no cover - safety net
        app.logger.exception("Unhandled exception")
        return error_response(500, "internal_error", "An internal error occurred.")
