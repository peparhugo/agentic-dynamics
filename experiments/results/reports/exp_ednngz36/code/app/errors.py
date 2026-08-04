"""Consistent JSON error handling.

Every error response uses the envelope:
    {"error": {"code": "<machine_code>", "message": "<human message>", "details": {...}}}
"""
from flask import jsonify
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message, code=None, status_code=None, details=None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}


class ValidationFailure(APIError):
    status_code = 422
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


def error_response(status_code, code, message, details=None, headers=None):
    body = {"error": {"code": code, "message": message, "details": details or {}}}
    resp = jsonify(body)
    resp.status_code = status_code
    if headers:
        for k, v in headers.items():
            resp.headers[k] = v
    return resp


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(err):
        headers = None
        if isinstance(err, RateLimitError):
            retry_after = err.details.get("retry_after")
            if retry_after is not None:
                headers = {"Retry-After": str(retry_after)}
        return error_response(err.status_code, err.code, err.message, err.details, headers)

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        code = (err.name or "error").lower().replace(" ", "_")
        return error_response(err.code, code, err.description)

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        if app.config.get("TESTING") and app.config.get("RAISE_UNEXPECTED"):
            raise err
        app.logger.exception("Unhandled exception")
        return error_response(500, "internal_error", "An unexpected error occurred.")
