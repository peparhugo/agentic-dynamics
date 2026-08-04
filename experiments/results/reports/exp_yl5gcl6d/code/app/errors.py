"""Consistent JSON error handling.

All errors are rendered as:
    {"error": {"code": "<machine_code>", "message": "<human message>", "details": {...}}}
"""
from flask import jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    """Application-level error carrying an HTTP status and machine-readable code."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, status_code: int | None = None,
                 code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.details = details or {}


class ValidationApiError(ApiError):
    status_code = 422
    code = "validation_error"


class AuthError(ApiError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(ApiError):
    status_code = 403
    code = "forbidden"


class NotFoundError(ApiError):
    status_code = 404
    code = "not_found"


class ConflictError(ApiError):
    status_code = 409
    code = "conflict"


class RateLimitError(ApiError):
    status_code = 429
    code = "rate_limit_exceeded"

    def __init__(self, message: str = "Rate limit exceeded", *, retry_after: int = 0,
                 details: dict | None = None):
        super().__init__(message, details=details)
        self.retry_after = retry_after


def error_response(status_code: int, code: str, message: str, details: dict | None = None):
    payload = {"error": {"code": code, "message": message, "details": details or {}}}
    response = jsonify(payload)
    response.status_code = status_code
    return response


HTTP_CODE_NAMES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limit_exceeded",
    500: "internal_server_error",
}


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        response = error_response(err.status_code, err.code, err.message, err.details)
        if isinstance(err, RateLimitError) and err.retry_after:
            response.headers["Retry-After"] = str(err.retry_after)
        return response

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        code = HTTP_CODE_NAMES.get(err.code, "error")
        return error_response(err.code or 500, code, err.description or err.name)

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        app.logger.exception("Unhandled exception")
        if app.config.get("TESTING") and app.config.get("RAISE_UNHANDLED"):
            raise err
        return error_response(500, "internal_server_error",
                              "An unexpected error occurred.")
