"""Centralized error handling with a consistent JSON envelope.

Every error response has the shape:

    {
        "error": {
            "code": "<machine_readable_code>",
            "message": "<human readable message>",
            "details": {...}   # optional
        }
    }
"""
from flask import jsonify
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    """Application-level error that maps cleanly to an HTTP response."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message, status_code=None, code=None, details=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.details = details


class NotFoundError(ApiError):
    status_code = 404
    code = "not_found"


class UnauthorizedError(ApiError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(ApiError):
    status_code = 403
    code = "forbidden"


class ConflictError(ApiError):
    status_code = 409
    code = "conflict"


def error_response(status_code, code, message, details=None):
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return jsonify(body), status_code


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return error_response(err.status_code, err.code, err.message, err.details)

    @app.errorhandler(ValidationError)
    def handle_validation_error(err):
        return error_response(
            422, "validation_error", "Input validation failed.", err.messages
        )

    @app.errorhandler(HTTPException)
    def handle_http_exception(err):
        code_map = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
            429: "rate_limit_exceeded",
        }
        code = code_map.get(err.code, "http_error")
        return error_response(err.code or 500, code, err.description)

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        app.logger.exception("Unhandled exception")
        return error_response(500, "internal_error", "An unexpected error occurred.")
