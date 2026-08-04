"""Consistent JSON error handling.

Every error response has the shape:

    {"error": {"code": "<machine_code>", "message": "<human message>",
               "details": {...}}}
"""
from flask import jsonify
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message=None, *, code=None, status_code=None, details=None):
        super().__init__(message)
        self.message = message or self.__class__.__name__
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or {}


class ValidationError(APIError):
    status_code = 400
    code = "validation_error"


class AuthError(APIError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(APIError):
    status_code = 403
    code = "forbidden"


class NotFoundError(APIError):
    status_code = 404
    code = "not_found"


class ConflictError(APIError):
    status_code = 409
    code = "conflict"


class RateLimitError(APIError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, message="Rate limit exceeded", *, retry_after=None, **kw):
        super().__init__(message, **kw)
        self.retry_after = retry_after


def _error_body(code, message, details=None):
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(err: APIError):
        resp = jsonify(_error_body(err.code, err.message, err.details))
        resp.status_code = err.status_code
        if isinstance(err, RateLimitError) and err.retry_after is not None:
            resp.headers["Retry-After"] = str(err.retry_after)
        return resp

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException):
        code = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
            415: "unsupported_media_type",
        }.get(err.code, "http_error")
        resp = jsonify(_error_body(code, err.description))
        resp.status_code = err.code or 500
        return resp

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        app.logger.exception("Unhandled exception")
        resp = jsonify(_error_body("internal_error", "An unexpected error occurred"))
        resp.status_code = 500
        return resp
