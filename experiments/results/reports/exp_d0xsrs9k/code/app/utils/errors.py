from flask import request


class ValidationError(Exception):
    status_code = 422

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}


class NotFoundError(Exception):
    status_code = 404

    def __init__(self, message: str, error_type: str = "not_found"):
        self.message = message
        self.error_type = error_type


class ConflictError(Exception):
    status_code = 409

    def __init__(self, message: str, error_type: str = "conflict"):
        self.message = message
        self.error_type = error_type


def register_error_handlers(app):
    from app.middleware.auth import AuthError, ForbiddenError

    @app.errorhandler(AuthError)
    def handle_auth_error(error):
        return {
            "error": error.error_type,
            "message": error.message,
        }, error.status_code

    @app.errorhandler(ForbiddenError)
    def handle_forbidden_error(error):
        return {
            "error": error.error_type,
            "message": error.message,
        }, error.status_code

    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return {
            "error": "validation_error",
            "message": error.message,
            "details": error.details,
        }, error.status_code

    @app.errorhandler(NotFoundError)
    def handle_not_found_error(error):
        return {
            "error": error.error_type,
            "message": error.message,
        }, error.status_code

    @app.errorhandler(ConflictError)
    def handle_conflict_error(error):
        return {
            "error": error.error_type,
            "message": error.message,
        }, error.status_code

    @app.errorhandler(404)
    def handle_404(error):
        return {
            "error": "not_found",
            "message": "The requested resource was not found",
        }, 404

    @app.errorhandler(405)
    def handle_405(error):
        return {
            "error": "method_not_allowed",
            "message": "The method is not allowed for this endpoint",
        }, 405

    @app.errorhandler(500)
    def handle_500(error):
        return {
            "error": "internal_server_error",
            "message": "An internal server error occurred",
        }, 500

    @app.errorhandler(Exception)
    def handle_unhandled(error):
        import logging
        logger = logging.getLogger("audit")
        logger.error("Unhandled exception", exc_info=error)
        return {
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
        }, 500
