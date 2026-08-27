from flask import jsonify


class APIError(Exception):
    """Base exception carrying an HTTP status code and message."""

    status_code = 400

    def __init__(self, message, status_code=None, code=None, fields=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.code = code
        self.fields = fields

    def to_dict(self):
        payload = {
            "error": self.code or self.message,
            "message": self.message,
            "status_code": self.status_code,
        }
        if self.fields:
            payload["fields"] = self.fields
        return payload


class NotFoundError(APIError):
    status_code = 404

    def __init__(self, message="Resource not found"):
        super().__init__(message, status_code=404, code="not_found")


class ConflictError(APIError):
    status_code = 409

    def __init__(self, message="Resource already exists"):
        super().__init__(message, status_code=409, code="conflict")


class ValidationError(APIError):
    status_code = 422

    def __init__(self, message="Validation failed", fields=None):
        super().__init__(
            message, status_code=422, code="validation_error", fields=fields
        )


class UnauthorizedError(APIError):
    status_code = 401

    def __init__(self, message="Authentication required"):
        super().__init__(message, status_code=401, code="unauthorized")


class ForbiddenError(APIError):
    status_code = 403

    def __init__(self, message="You do not have permission to perform this action"):
        super().__init__(message, status_code=403, code="forbidden")


class RateLimitError(APIError):
    status_code = 429

    def __init__(self, message="Too many requests", retry_after=None):
        super().__init__(message, status_code=429, code="rate_limited")
        self.retry_after = retry_after


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(err):
        response = jsonify(err.to_dict())
        response.status_code = err.status_code
        if isinstance(err, RateLimitError) and err.retry_after is not None:
            response.headers["Retry-After"] = str(int(err.retry_after))
        return response

    @app.errorhandler(404)
    def handle_not_found(err):
        return jsonify(
            {
                "error": "not_found",
                "message": "The requested URL was not found on the server.",
                "status_code": 404,
            }
        ), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(err):
        return jsonify(
            {
                "error": "method_not_allowed",
                "message": "The method is not allowed for the requested URL.",
                "status_code": 405,
            }
        ), 405

    @app.errorhandler(400)
    def handle_bad_request(err):
        return jsonify(
            {
                "error": "bad_request",
                "message": err.description or "Bad request",
                "status_code": 400,
            }
        ), 400

    @app.errorhandler(500)
    def handle_internal_error(err):
        return jsonify(
            {
                "error": "internal_error",
                "message": "An internal server error occurred.",
                "status_code": 500,
            }
        ), 500
