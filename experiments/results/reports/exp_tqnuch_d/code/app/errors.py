from flask import jsonify
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException, default_exceptions


def register_error_handlers(app):

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "Bad Request", "message": str(error)}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return (
            jsonify(
                {
                    "error": "Unauthorized",
                    "message": "Authentication is required to access this resource.",
                }
            ),
            401,
        )

    @app.errorhandler(403)
    def forbidden(error):
        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": "You do not have permission to perform this action.",
                }
            ),
            403,
        )

    @app.errorhandler(404)
    def not_found(error):
        return (
            jsonify(
                {"error": "Not Found", "message": "The requested resource was not found."}
            ),
            404,
        )

    @app.errorhandler(405)
    def method_not_allowed(error):
        return (
            jsonify(
                {
                    "error": "Method Not Allowed",
                    "message": "The HTTP method is not allowed for this endpoint.",
                }
            ),
            405,
        )

    @app.errorhandler(429)
    def ratelimit_exceeded(error):
        return (
            jsonify(
                {
                    "error": "Too Many Requests",
                    "message": "Rate limit exceeded. Please try again later.",
                    "retry_after": error.description if error.description else None,
                }
            ),
            429,
        )

    @app.errorhandler(500)
    def internal_server_error(error):
        return (
            jsonify(
                {
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred.",
                }
            ),
            500,
        )

    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return (
            jsonify(
                {
                    "error": "Validation Error",
                    "messages": error.messages,
                }
            ),
            422,
        )

    @app.errorhandler(Exception)
    def handle_unhandled(error):
        if isinstance(error, HTTPException):
            return (
                jsonify(
                    {"error": error.name, "message": error.description}
                ),
                error.code,
            )
        return (
            jsonify(
                {
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred.",
                }
            ),
            500,
        )
