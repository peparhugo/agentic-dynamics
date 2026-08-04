from flask import jsonify


class AppError(Exception):
    def __init__(self, message="An error occurred", status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ValidationError(AppError):
    def __init__(self, message="Validation error"):
        super().__init__(message, 422)


class AuthenticationError(AppError):
    def __init__(self, message="Authentication failed"):
        super().__init__(message, 401)


class ForbiddenError(AppError):
    def __init__(self, message="Forbidden"):
        super().__init__(message, 403)


class NotFoundError(AppError):
    def __init__(self, message="Not found"):
        super().__init__(message, 404)


class ConflictError(AppError):
    def __init__(self, message="Conflict"):
        super().__init__(message, 409)


class TooManyRequestsError(AppError):
    def __init__(self, message="Too many requests"):
        super().__init__(message, 429)


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(error):
        return jsonify({"error": error.message}), error.status_code

    @app.errorhandler(400)
    def handle_bad_request(error):
        return jsonify({"error": "Bad request"}), 400

    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def handle_internal_error(error):
        return jsonify({"error": "Internal server error"}), 500
