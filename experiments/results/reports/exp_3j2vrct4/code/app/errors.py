"""Consistent JSON error handling.

All errors are returned in the envelope:
    {"error": {"code": "...", "message": "...", "details": {...}}}
"""
from flask import jsonify
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    status_code = 500
    code = "internal_error"
    message = "An unexpected error occurred."

    def __init__(self, message=None, details=None, code=None, status_code=None):
        super().__init__(message or self.message)
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details


class ValidationError(APIError):
    status_code = 400
    code = "validation_error"
    message = "Request validation failed."


class AuthenticationError(APIError):
    status_code = 401
    code = "authentication_required"
    message = "Authentication required."


class ForbiddenError(APIError):
    status_code = 403
    code = "forbidden"
    message = "You do not have access to this resource."


class NotFoundError(APIError):
    status_code = 404
    code = "not_found"
    message = "Resource not found."


class ConflictError(APIError):
    status_code = 409
    code = "conflict"
    message = "Resource conflict."


class RateLimitError(APIError):
    status_code = 429
    code = "rate_limit_exceeded"
    message = "Too many requests."


def _error_body(code, message, details=None):
    err = {"code": code, "message": message}
    if details:
        err["details"] = details
    return {"error": err}


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(exc: APIError):
        resp = jsonify(_error_body(exc.code, exc.message, exc.details))
        resp.status_code = exc.status_code
        if isinstance(exc, RateLimitError) and exc.details:
            retry = exc.details.get("retry_after")
            if retry is not None:
                resp.headers["Retry-After"] = str(retry)
        return resp

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        code = (exc.name or "error").lower().replace(" ", "_")
        resp = jsonify(_error_body(code, exc.description or exc.name))
        resp.status_code = exc.code or 500
        return resp

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):  # pragma: no cover - safety net
        app.logger.exception("Unhandled exception")
        resp = jsonify(_error_body("internal_error", "An unexpected error occurred."))
        resp.status_code = 500
        return resp
