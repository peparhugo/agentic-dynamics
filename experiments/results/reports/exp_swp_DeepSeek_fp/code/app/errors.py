from flask import jsonify
from sqlalchemy.exc import IntegrityError

from .extensions import db


class APIError(Exception):
    def __init__(self, message, status_code=400, code=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code or "error"


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(e):
        return jsonify({"error": e.message, "code": e.code}), e.status_code

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(e):
        db.session.rollback()
        return jsonify({"error": "Resource already exists", "code": "conflict"}), 409

    @app.errorhandler(400)
    def handle_bad_request(e):
        return jsonify({"error": "Bad request", "code": "bad_request"}), 400

    @app.errorhandler(401)
    def handle_unauthorized(e):
        return jsonify({"error": "Unauthorized", "code": "unauthorized"}), 401

    @app.errorhandler(403)
    def handle_forbidden(e):
        return jsonify({"error": "Forbidden", "code": "forbidden"}), 403

    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({"error": "Resource not found", "code": "not_found"}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        return jsonify({"error": "Method not allowed", "code": "method_not_allowed"}), 405

    @app.errorhandler(413)
    def handle_too_large(e):
        return jsonify({"error": "Request entity too large", "code": "payload_too_large"}), 413

    @app.errorhandler(429)
    def handle_rate_limited(e):
        return jsonify({"error": "Too many requests", "code": "rate_limited"}), 429

    @app.errorhandler(Exception)
    def handle_unhandled(e):
        app.logger.exception(e)
        return jsonify({"error": "Internal server error", "code": "internal_error"}), 500
