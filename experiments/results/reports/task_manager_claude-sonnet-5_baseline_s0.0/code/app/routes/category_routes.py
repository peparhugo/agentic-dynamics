from flask import Blueprint, g, jsonify, request

from app import models
from app.auth import token_required
from app.utils import get_pagination_params, paginated_response

category_bp = Blueprint("categories", __name__)


@category_bp.post("")
@token_required
def create_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    try:
        category = models.create_category(name, g.current_user["id"])
    except ValueError:
        return jsonify({"error": "category with this name already exists"}), 409

    return jsonify({"category": category}), 201


@category_bp.get("")
@token_required
def list_categories():
    page, per_page = get_pagination_params()
    categories, total = models.list_categories(g.current_user["id"], page, per_page)
    return jsonify(paginated_response(categories, total, page, per_page, key="categories")), 200


@category_bp.get("/<int:category_id>")
@token_required
def get_category(category_id):
    category = models.get_category_by_id(category_id, g.current_user["id"])
    if category is None:
        return jsonify({"error": "category not found"}), 404
    return jsonify({"category": category}), 200


@category_bp.put("/<int:category_id>")
@token_required
def update_category(category_id):
    existing = models.get_category_by_id(category_id, g.current_user["id"])
    if existing is None:
        return jsonify({"error": "category not found"}), 404

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    try:
        category = models.update_category(category_id, g.current_user["id"], name)
    except ValueError:
        return jsonify({"error": "category with this name already exists"}), 409

    return jsonify({"category": category}), 200


@category_bp.delete("/<int:category_id>")
@token_required
def delete_category(category_id):
    existing = models.get_category_by_id(category_id, g.current_user["id"])
    if existing is None:
        return jsonify({"error": "category not found"}), 404

    models.delete_category(category_id, g.current_user["id"])
    return "", 204
