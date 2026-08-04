from flask import jsonify


class APIError(Exception):
    def __init__(self, message, status_code=400, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class AuthenticationError(APIError):
    def __init__(self, message="Authentication required", details=None):
        super().__init__(message, status_code=401, details=details)


class ForbiddenError(APIError):
    def __init__(self, message="Forbidden", details=None):
        super().__init__(message, status_code=403, details=details)


class NotFoundError(APIError):
    def __init__(self, message="Resource not found", details=None):
        super().__init__(message, status_code=404, details=details)


class ValidationError(APIError):
    def __init__(self, message="Validation failed", details=None):
        super().__init__(message, status_code=422, details=details)


class RateLimitError(APIError):
    def __init__(self, message="Too many requests", details=None):
        super().__init__(message, status_code=429, details=details)


class ConflictError(APIError):
    def __init__(self, message="Conflict", details=None):
        super().__init__(message, status_code=409, details=details)


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(error):
        response = {
            "error": {
                "code": error.status_code,
                "message": error.message,
                "details": error.details,
            }
        }
        return jsonify(response), error.status_code

    @app.errorhandler(400)
    def handle_400(error):
        return jsonify({
            "error": {
                "code": 400,
                "message": "Bad request",
                "details": str(error),
            }
        }), 400

    @app.errorhandler(404)
    def handle_404(error):
        return jsonify({
            "error": {
                "code": 404,
                "message": "Not found",
                "details": str(error),
            }
        }), 404

    @app.errorhandler(405)
    def handle_405(error):
        return jsonify({
            "error": {
                "code": 405,
                "message": "Method not allowed",
                "details": str(error),
            }
        }), 405

    @app.errorhandler(429)
    def handle_429(error):
        return jsonify({
            "error": {
                "code": 429,
                "message": "Too many requests",
                "details": str(error),
            }
        }), 429

    @app.errorhandler(500)
    def handle_500(error):
        return jsonify({
            "error": {
                "code": 500,
                "message": "Internal server error",
                "details": str(error) if app.debug else "An unexpected error occurred",
            }
        }), 500
