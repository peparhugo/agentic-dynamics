from flask import jsonify
from werkzeug.exceptions import HTTPException


def register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        response = {
            "error": error.name,
            "message": error.description,
        }
        return jsonify(response), error.code

    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({"error": "Not Found", "message": "Resource not found"}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        return jsonify({"error": "Method Not Allowed", "message": str(error)}), 405

    @app.errorhandler(400)
    def handle_bad_request(error):
        return jsonify({"error": "Bad Request", "message": str(error)}), 400

    @app.errorhandler(Exception)
    def handle_unhandled(error):
        app.logger.exception(error)
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred"}), 500
