from flask import jsonify
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException


def register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        return {
            "error": e.description,
            "code": e.__class__.__name__.upper(),
        }, e.code

    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        return {
            "error": "Validation failed",
            "code": "VALIDATION_ERROR",
            "details": e.messages,
        }, 422

    @app.errorhandler(400)
    def handle_bad_request(e):
        return {
            "error": str(e.description) if hasattr(e, 'description') else "Bad request",
            "code": "BAD_REQUEST",
        }, 400

    @app.errorhandler(404)
    def handle_not_found(e):
        return {
            "error": "Resource not found",
            "code": "NOT_FOUND",
        }, 404

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        return {
            "error": "Method not allowed",
            "code": "METHOD_NOT_ALLOWED",
        }, 405

    @app.errorhandler(500)
    def handle_internal_error(e):
        return {
            "error": "Internal server error",
            "code": "INTERNAL_ERROR",
        }, 500

    @app.errorhandler(Exception)
    def handle_unhandled_error(e):
        app.logger.exception("Unhandled error: %s", str(e))
        return {
            "error": "Internal server error",
            "code": "INTERNAL_ERROR",
        }, 500
