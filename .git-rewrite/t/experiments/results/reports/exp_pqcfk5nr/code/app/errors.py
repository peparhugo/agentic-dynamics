from __future__ import annotations

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException, BadRequest, NotFound, Unauthorized, Forbidden
from marshmallow import ValidationError as MarshmallowValidationError


class ValidationError(BadRequest):
    description = "Input validation failed"


def error_response(status: int, message: str, code: str | None = None, details: dict | None = None):
    payload = {"error": {"message": message}}
    if code:
        payload["error"]["code"] = code
    if details:
        payload["error"]["details"] = details
    return jsonify(payload), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ValidationError)
    def handle_validation(err: ValidationError):
        return error_response(400, err.description, code="validation_error", details=getattr(err, "data", None))

    @app.errorhandler(MarshmallowValidationError)
    def handle_marshmallow_validation(err: MarshmallowValidationError):
        return error_response(400, "Input validation failed", code="validation_error", details=err.messages)

    @app.errorhandler(HTTPException)
    def handle_http(err: HTTPException):
        return error_response(err.code or 500, err.description or "HTTP error")

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        # In production, avoid leaking internals
        if app.testing:
            return error_response(500, "Internal server error", details={"type": type(err).__name__, "msg": str(err)})
        return error_response(500, "Internal server error")
