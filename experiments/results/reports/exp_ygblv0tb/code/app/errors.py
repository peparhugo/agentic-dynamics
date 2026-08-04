from flask import jsonify
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    """Application-level error with a stable JSON shape."""

    def __init__(self, message, status_code=400, code=None, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code or self._default_code(status_code)
        self.details = details

    @staticmethod
    def _default_code(status_code):
        return {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            422: "unprocessable_entity",
            429: "rate_limited",
        }.get(status_code, "error")


def _error_body(code, message, status, details=None):
    body = {"error": {"code": code, "message": message, "status": status}}
    if details:
        body["error"]["details"] = details
    return body


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return jsonify(_error_body(err.code, err.message, err.status_code,
                                   err.details)), err.status_code

    @app.errorhandler(ValidationError)
    def handle_validation_error(err):
        return jsonify(_error_body("validation_error", "Input validation failed",
                                   400, err.messages)), 400

    @app.errorhandler(429)
    def handle_rate_limit(err):
        return jsonify(_error_body("rate_limited",
                                   f"Rate limit exceeded: {err.description}",
                                   429)), 429

    @app.errorhandler(HTTPException)
    def handle_http_exception(err):
        code = (err.name or "error").lower().replace(" ", "_")
        return jsonify(_error_body(code, err.description, err.code)), err.code

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        app.logger.exception("Unhandled exception")
        return jsonify(_error_body("internal_error",
                                   "An unexpected error occurred", 500)), 500
