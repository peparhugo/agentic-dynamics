from flask import jsonify
from werkzeug.exceptions import HTTPException


class APIError(Exception):
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

    def to_dict(self):
        body = {
            "code": self.error_code,
            "message": self.message,
        }
        if self.details is not None:
            body["details"] = self.details
        return {"error": body}


class ValidationError(APIError):
    status_code = 400
    error_code = "validation_error"


class UnauthorizedError(APIError):
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


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(err):
        return jsonify(err.to_dict()), err.status_code

    @app.errorhandler(HTTPException)
    def handle_http_exception(err):
        code = err.code if err.code else 500
        return (
            jsonify({"error": {"code": err.name.lower().replace(" ", "_"), "message": err.description}}),
            code,
        )

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        app.logger.exception("Unhandled error: %s", err)
        return (
            jsonify({"error": {"code": "internal_server_error", "message": "An unexpected error occurred"}}),
            500,
        )
