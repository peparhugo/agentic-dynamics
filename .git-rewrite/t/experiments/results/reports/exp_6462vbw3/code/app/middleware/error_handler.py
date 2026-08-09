from flask import Blueprint, jsonify
from werkzeug.exceptions import HTTPException


errors_bp = Blueprint("errors", __name__)


@errors_bp.app_errorhandler(400)
def bad_request(e):
    return jsonify(error="Bad request", message=str(e.description if hasattr(e, "description") else e)), 400


@errors_bp.app_errorhandler(401)
def unauthorized(e):
    return jsonify(error="Unauthorized", message=str(e.description if hasattr(e, "description") else e)), 401


@errors_bp.app_errorhandler(403)
def forbidden(e):
    return jsonify(error="Forbidden", message=str(e.description if hasattr(e, "description") else e)), 403


@errors_bp.app_errorhandler(404)
def not_found(e):
    return jsonify(error="Not found", message=str(e.description if hasattr(e, "description") else e)), 404


@errors_bp.app_errorhandler(422)
def unprocessable(e):
    return jsonify(error="Unprocessable entity", message=str(e.description if hasattr(e, "description") else e)), 422


@errors_bp.app_errorhandler(429)
def too_many_requests(e):
    return jsonify(error="Rate limit exceeded", message=str(e.description)), 429


@errors_bp.app_errorhandler(500)
def internal_error(e):
    return jsonify(error="Internal server error", message="An unexpected error occurred"), 500


@errors_bp.app_errorhandler(Exception)
def handle_generic(e):
    if isinstance(e, HTTPException):
        return jsonify(error=e.name, message=e.description), e.code
    return jsonify(error="Internal server error", message=str(e)), 500
