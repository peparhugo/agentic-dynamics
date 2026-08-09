from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from ..models.category import (
    create_category,
    get_category_by_id,
    get_category_by_name,
    get_all_categories,
    update_category,
    delete_category,
    category_to_dict,
)

categories_bp = Blueprint("categories", __name__)


@categories_bp.route("", methods=["POST"])
@jwt_required()
def create():
    data = request.get_json(silent=True) or {}

    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Category name is required."}), 400

    if get_category_by_name(name):
        return jsonify({"error": "A category with that name already exists."}), 409

    color = data.get("color", "#3B82F6")
    cat_id = create_category(name, color)
    if cat_id is None:
        return jsonify({"error": "Could not create category."}), 500

    category = get_category_by_id(cat_id)
    return jsonify({"category": category_to_dict(category)}), 201


@categories_bp.route("", methods=["GET"])
@jwt_required()
def list_categories():
    categories = get_all_categories()
    return jsonify({
        "categories": [category_to_dict(c) for c in categories]
    }), 200


@categories_bp.route("/<int:category_id>", methods=["GET"])
@jwt_required()
def get(category_id):
    category = get_category_by_id(category_id)
    if not category:
        return jsonify({"error": "Category not found."}), 404
    return jsonify({"category": category_to_dict(category)}), 200


@categories_bp.route("/<int:category_id>", methods=["PUT"])
@jwt_required()
def update(category_id):
    category = get_category_by_id(category_id)
    if not category:
        return jsonify({"error": "Category not found."}), 404

    data = request.get_json(silent=True) or {}

    name = data.get("name", "").strip() or None
    color = data.get("color") or None

    if name and name != category["name"] and get_category_by_name(name):
        return jsonify({"error": "A category with that name already exists."}), 409

    if not name and not color:
        return jsonify({"error": "No valid fields to update."}), 400

    update_category(category_id, name=name, color=color)
    category = get_category_by_id(category_id)
    return jsonify({"category": category_to_dict(category)}), 200


@categories_bp.route("/<int:category_id>", methods=["DELETE"])
@jwt_required()
def delete(category_id):
    category = get_category_by_id(category_id)
    if not category:
        return jsonify({"error": "Category not found."}), 404

    delete_category(category_id)
    return jsonify({"message": "Category deleted."}), 200
