"""Consistent JSON error handling.

Every error response uses the envelope:
    {"error": {"code": <machine-readable>, "message": <human-readable>, "details": {...}}}
"""
from flask import Flask, jsonify
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    """Raise anywhere in a request to produce a structured JSON error."""

    def __init__(self, message: str, status_code: int = 400, code: str = "bad_request", details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}


def error_response(status_code: int, code: str, message: str, details=None):
    payload = {"error": {"code": code, "message": message, "details": details or {}}}
    return jsonify(payload), status_code


_HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    415: "unsupported_media_type",
    422: "unprocessable_entity",
    429: "rate_limit_exceeded",
    500: "internal_server_error",
}


def register_jwt_error_handlers(jwt) -> None:
    """Make Flask-JWT-Extended failures use the same error envelope."""

    @jwt.unauthorized_loader
    def missing_token(reason):
        return error_response(401, "authorization_required", reason)

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return error_response(401, "invalid_token", reason)

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return error_response(401, "token_expired", "Token has expired.")


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        return error_response(err.status_code, err.code, err.message, err.details)

    @app.errorhandler(ValidationError)
    def handle_validation_error(err: ValidationError):
        return error_response(422, "validation_error", "Input validation failed.", err.messages)

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        code = _HTTP_CODES.get(err.code, "error")
        return error_response(err.code or 500, code, err.description or err.name)

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):  # pragma: no cover - safety net
        app.logger.exception("Unhandled exception")
        if app.config.get("TESTING") or app.config.get("DEBUG"):
            raise err
        return error_response(500, "internal_server_error", "An unexpected error occurred.")
