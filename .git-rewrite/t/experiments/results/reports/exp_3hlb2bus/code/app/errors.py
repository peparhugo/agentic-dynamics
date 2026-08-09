"""Consistent JSON error responses."""
from flask import jsonify
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    """Raise anywhere in a view to return a JSON error with a status code."""

    def __init__(self, message, status_code=400, payload=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}

    def to_response(self):
        body = {"error": self.message, **self.payload}
        return jsonify(body), self.status_code


def init_app(app):
    @app.errorhandler(APIError)
    def handle_api_error(err):
        return err.to_response()

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        return jsonify({"error": err.description}), err.code

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        if app.config.get("TESTING") or app.debug:
            raise err
        return jsonify({"error": "Internal server error"}), 500
