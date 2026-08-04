from flask import jsonify
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, details=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.details = details


class ValidationError(APIError):
    status_code = 422


class AuthError(APIError):
    status_code = 401


class ForbiddenError(APIError):
    status_code = 403


class NotFoundError(APIError):
    status_code = 404


class ConflictError(APIError):
    status_code = 409


class RateLimitError(APIError):
    status_code = 429

    def __init__(self, message="rate limit exceeded", retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


def _payload(message, details=None):
    body = {"error": message}
    if details:
        body["details"] = details
    return body


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(e):
        resp = jsonify(_payload(e.message, e.details))
        resp.status_code = e.status_code
        if isinstance(e, RateLimitError) and e.retry_after is not None:
            resp.headers["Retry-After"] = str(e.retry_after)
        return resp

    @app.errorhandler(HTTPException)
    def handle_http_error(e):
        return jsonify(_payload(e.description or e.name)), e.code

    @app.errorhandler(Exception)
    def handle_unexpected(e):
        return jsonify(_payload("internal server error")), 500
