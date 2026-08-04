from flask import jsonify


class AppError(Exception):
    def __init__(self, message, status_code=400, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "message": str(e)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Unauthorized", "message": "Authentication required"}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Forbidden", "message": "You do not have permission"}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found", "message": str(e)}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed", "message": str(e)}), 405

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return jsonify({"error": "Rate limit exceeded", "message": str(e), "retry_after": getattr(e, "retry_after", None)}), 429

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "Internal server error", "message": "An unexpected error occurred"}), 500

    @app.errorhandler(AppError)
    def handle_app_error(e):
        response = {"error": e.message}
        if e.details:
            response["details"] = e.details
        return jsonify(response), e.status_code
