from flask import jsonify
from werkzeug.exceptions import HTTPException


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "bad request", "message": str(error)}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({"error": "unauthorized", "message": str(error)}), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({"error": "forbidden", "message": str(error)}), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "not found", "message": str(error)}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({"error": "method not allowed", "message": str(error)}), 405

    @app.errorhandler(429)
    def too_many_requests(error):
        return jsonify({"error": "too many requests", "message": str(error)}), 429

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "internal server error"}), 500

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        return (
            jsonify({"error": error.name.lower().replace(" ", "_"), "message": error.description}),
            error.code,
        )
