from flask import jsonify
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    def __init__(self, status, code, message, details=None, headers=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers or {}


def error_response(status, code, message, details=None):
    payload = {"error": {"code": code, "message": message}}
    if details:
        payload["error"]["details"] = details
    return jsonify(payload), status


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(error):
        response, status = error_response(
            error.status, error.code, error.message, error.details
        )
        response.headers.update(error.headers)
        return response, status

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        code = error.name.lower().replace(" ", "_")
        return error_response(error.code, code, error.description)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if app.config["TESTING"]:
            raise error
        app.logger.exception("Unhandled API error")
        return error_response(500, "internal_error", "An internal error occurred")
