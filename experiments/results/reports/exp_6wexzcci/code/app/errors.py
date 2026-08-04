"""Consistent JSON error envelope for the whole API."""
from flask import jsonify
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    """Application-level error carrying an HTTP status and machine-readable code."""

    status_code = 400
    error_code = "bad_request"

    def __init__(self, message, status_code=None, error_code=None, details=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        self.details = details


class ValidationAPIError(APIError):
    status_code = 422
    error_code = "validation_error"


class AuthError(APIError):
    status_code = 401
    error_code = "unauthorized"


class ForbiddenError(APIError):
    status_code = 403
    error_code = "forbidden"


class NotFoundError(APIError):
    status_code = 404
    error_code = "not_found"


class ConflictError(APIError):
    status_code = 409
    error_code = "conflict"


class RateLimitError(APIError):
    status_code = 429
    error_code = "rate_limited"


def _envelope(code, message, status, details=None):
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    resp = jsonify(body)
    resp.status_code = status
    return resp


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(err):
        resp = _envelope(err.error_code, err.message, err.status_code, err.details)
        if isinstance(err, RateLimitError) and err.details and "retry_after" in err.details:
            resp.headers["Retry-After"] = str(err.details["retry_after"])
        return resp

    @app.errorhandler(HTTPException)
    def handle_http_exception(err):
        code = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
            415: "unsupported_media_type",
        }.get(err.code, "http_error")
        return _envelope(code, err.description, err.code)

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        app.logger.exception("Unhandled exception")
        return _envelope("internal_error", "An internal error occurred.", 500)
