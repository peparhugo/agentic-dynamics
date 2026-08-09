from flask import Blueprint, jsonify, request
from werkzeug.exceptions import HTTPException

errors_bp = Blueprint("errors", __name__)


@errors_bp.app_errorhandler(400)
def bad_request(error):
    return jsonify({"error": "Bad request", "message": str(error)}), 400


@errors_bp.app_errorhandler(401)
def unauthorized(error):
    return jsonify({"error": "Unauthorized", "message": str(error)}), 401


@errors_bp.app_errorhandler(403)
def forbidden(error):
    return jsonify({"error": "Forbidden", "message": str(error)}), 403


@errors_bp.app_errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found", "message": "The requested resource was not found"}), 404


@errors_bp.app_errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Method not allowed", "message": str(error)}), 405


@errors_bp.app_errorhandler(422)
def unprocessable_entity(error):
    return jsonify({"error": "Unprocessable entity", "message": str(error)}), 422


@errors_bp.app_errorhandler(429)
def too_many_requests(error):
    return jsonify({
        "error": "Too many requests",
        "message": "Rate limit exceeded. Please try again later.",
    }), 429


@errors_bp.app_errorhandler(500)
def internal_server_error(error):
    return jsonify({"error": "Internal server error", "message": "An unexpected error occurred"}), 500


@errors_bp.app_errorhandler(Exception)
def handle_unhandled(error):
    if isinstance(error, HTTPException):
        return jsonify({"error": error.name, "message": error.description}), error.code
    return jsonify({"error": "Internal server error", "message": "An unexpected error occurred"}), 500
