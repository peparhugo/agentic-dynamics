from http import HTTPStatus
from flask import jsonify
from werkzeug.http import HTTP_STATUS_CODES


class APIError(Exception):
    def __init__(self, message=None, status_code=None, payload=None, code=None):
        super().__init__()
        self.message = message or "An error occurred"
        self.status_code = status_code or HTTPStatus.INTERNAL_SERVER_ERROR
        self.payload = payload or {}
        self.code = code or "internal_error"

    def to_dict(self):
        rv = {
            "error": {
                "code": self.code,
                "message": self.message,
                "status": self.status_code,
            }
        }
        if self.payload:
            rv["error"]["details"] = self.payload
        return rv


class BadRequestError(APIError):
    def __init__(self, message="Bad request", payload=None):
        super().__init__(message=message, status_code=HTTPStatus.BAD_REQUEST,
                         code="bad_request", payload=payload)


class ValidationError(APIError):
    def __init__(self, message="Validation failed", payload=None):
        super().__init__(message=message, status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                         code="validation_error", payload=payload)


class UnauthorizedError(APIError):
    def __init__(self, message="Authentication required"):
        super().__init__(message=message, status_code=HTTPStatus.UNAUTHORIZED,
                         code="unauthorized")


class ForbiddenError(APIError):
    def __init__(self, message="Insufficient permissions"):
        super().__init__(message=message, status_code=HTTPStatus.FORBIDDEN,
                         code="forbidden")


class NotFoundError(APIError):
    def __init__(self, message="Resource not found", resource=None, resource_id=None):
        payload = {}
        if resource:
            payload["resource"] = resource
        if resource_id:
            payload["resource_id"] = resource_id
        super().__init__(message=message, status_code=HTTPStatus.NOT_FOUND,
                         code="not_found", payload=payload)


class ConflictError(APIError):
    def __init__(self, message="Resource already exists"):
        super().__init__(message=message, status_code=HTTPStatus.CONFLICT,
                         code="conflict")


class RateLimitError(APIError):
    def __init__(self, message="Rate limit exceeded", retry_after=None):
        payload = {}
        if retry_after is not None:
            payload["retry_after"] = retry_after
        super().__init__(message=message, status_code=HTTPStatus.TOO_MANY_REQUESTS,
                         code="rate_limit_exceeded", payload=payload)


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(error):
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response

    @app.errorhandler(HTTPStatus.NOT_FOUND)
    def handle_404(error):
        return jsonify({
            "error": {
                "code": "not_found",
                "message": "The requested URL was not found on the server.",
                "status": HTTPStatus.NOT_FOUND,
            }
        }), HTTPStatus.NOT_FOUND

    @app.errorhandler(HTTPStatus.METHOD_NOT_ALLOWED)
    def handle_405(error):
        return jsonify({
            "error": {
                "code": "method_not_allowed",
                "message": "The method is not allowed for the requested URL.",
                "status": HTTPStatus.METHOD_NOT_ALLOWED,
            }
        }), HTTPStatus.METHOD_NOT_ALLOWED

    @app.errorhandler(HTTPStatus.TOO_MANY_REQUESTS)
    def handle_429(error):
        retry_after = error.description if isinstance(error.description, str) else None
        return jsonify({
            "error": {
                "code": "rate_limit_exceeded",
                "message": "Rate limit exceeded. Please try again later.",
                "status": HTTPStatus.TOO_MANY_REQUESTS,
                "details": {"retry_after": retry_after},
            }
        }), HTTPStatus.TOO_MANY_REQUESTS

    @app.errorhandler(HTTPStatus.INTERNAL_SERVER_ERROR)
    def handle_500(error):
        return jsonify({
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred.",
                "status": HTTPStatus.INTERNAL_SERVER_ERROR,
            }
        }), HTTPStatus.INTERNAL_SERVER_ERROR
