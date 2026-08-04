from flask import jsonify
from werkzeug.exceptions import HTTPException

from app.middleware.auth import AuthError


class APIError(Exception):
    def __init__(self, message, status_code=400, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def register_error_handlers(app):
    @app.errorhandler(AuthError)
    def handle_auth_error(error):
        return jsonify({"error": error.message}), error.status_code

    @app.errorhandler(APIError)
    def handle_api_error(error):
        payload = {"error": error.message}
        if error.details:
            payload["details"] = error.details
        return jsonify(payload), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        return (
            jsonify(
                {
                    "error": error.name.replace("_", " ").capitalize(),
                    "description": error.description,
                }
            ),
            error.code,
        )

    @app.errorhandler(429)
    def handle_rate_limit_error(error):
        return jsonify({"error": "Rate limit exceeded. Try again later."}), 429

    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def handle_internal_error(error):
        return jsonify({"error": "Internal server error"}), 500
