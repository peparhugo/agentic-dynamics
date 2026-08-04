from flask import request, jsonify
from werkzeug.exceptions import HTTPException


def parse_pagination_params(default_page=1, default_per_page=20, max_per_page=100):
    page = request.args.get("page", default_page, type=int)
    per_page = request.args.get("per_page", default_per_page, type=int)
    sort_by = request.args.get("sort_by", "created_at", type=str)
    order = request.args.get("order", "desc", type=str)

    if page < 1:
        page = 1
    if per_page < 1:
        per_page = default_per_page
    if per_page > max_per_page:
        per_page = max_per_page
    if order not in ("asc", "desc"):
        order = "desc"

    offset = (page - 1) * per_page
    return {
        "page": page,
        "per_page": per_page,
        "offset": offset,
        "sort_by": sort_by,
        "order": order,
    }


def build_paginated_response(items, total, page, per_page):
    total_pages = (total + per_page - 1) // per_page if total > 0 else 0
    return {
        "data": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "Bad request", "message": str(error)}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({"error": "Unauthorized", "message": str(error)}), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({"error": "Forbidden", "message": str(error)}), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found", "message": str(error)}), 404

    @app.errorhandler(409)
    def conflict(error):
        return jsonify({"error": "Conflict", "message": str(error)}), 409

    @app.errorhandler(422)
    def unprocessable_entity(error):
        return jsonify({"error": "Validation error", "message": str(error)}), 422

    @app.errorhandler(429)
    def too_many_requests(error):
        return (
            jsonify({"error": "Too many requests", "message": str(error)}),
            429,
        )

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Internal server error"}), 500

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        return (
            jsonify({"error": error.name, "message": error.description}),
            error.code,
        )
