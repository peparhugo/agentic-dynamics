from flask import jsonify
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException, TooManyRequests


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "Bad Request", "message": str(error)}), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not Found", "message": str(error)}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({"error": "Method Not Allowed", "message": str(error)}), 405

    @app.errorhandler(422)
    def unprocessable_entity(error):
        return jsonify({"error": "Unprocessable Entity", "message": str(error)}), 422

    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return jsonify({
            "error": "Too Many Requests",
            "message": "Rate limit exceeded. Please try again later.",
        }), 429

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            "error": "Internal Server Error",
            "message": "An unexpected error occurred.",
        }), 500

    @app.errorhandler(ValidationError)
    def validation_error(error):
        return jsonify({"error": "Validation Error", "messages": error.messages}), 422

    @app.errorhandler(HTTPException)
    def http_exception(error):
        return jsonify({
            "error": error.name,
            "message": error.description,
        }), error.code

    @app.errorhandler(Exception)
    def unhandled_exception(error):
        app.logger.exception("Unhandled exception: %s", str(error))
        return jsonify({
            "error": "Internal Server Error",
            "message": "An unexpected error occurred.",
        }), 500
