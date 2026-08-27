from flask import Blueprint, jsonify, request

from .extensions import db
from .models import Category
from .utils import token_required

categories_bp = Blueprint("categories", __name__, url_prefix="/api/categories")


@categories_bp.route("", methods=["POST"])
@token_required
def create_category(current_user):
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip() or None

    if not name:
        return jsonify({"error": "name is required"}), 400
    if Category.query.filter_by(name=name).first():
        return jsonify({"error": "category already exists"}), 409

    category = Category(name=name, description=description)
    db.session.add(category)
    db.session.commit()
    return jsonify(category.to_dict()), 201


@categories_bp.route("", methods=["GET"])
@token_required
def list_categories(current_user):
    categories = Category.query.order_by(Category.name).all()
    return jsonify([c.to_dict() for c in categories]), 200


@categories_bp.route("/<int:category_id>", methods=["GET"])
@token_required
def get_category(current_user, category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        return jsonify({"error": "category not found"}), 404
    return jsonify(category.to_dict()), 200


@categories_bp.route("/<int:category_id>", methods=["PUT"])
@token_required
def update_category(current_user, category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        return jsonify({"error": "category not found"}), 404

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if name:
        existing = Category.query.filter(
            Category.name == name, Category.id != category_id
        ).first()
        if existing:
            return jsonify({"error": "category already exists"}), 409
        category.name = name
    if "description" in data:
        category.description = (data.get("description") or "").strip() or None

    db.session.commit()
    return jsonify(category.to_dict()), 200


@categories_bp.route("/<int:category_id>", methods=["DELETE"])
@token_required
def delete_category(current_user, category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        return jsonify({"error": "category not found"}), 404
    if category.tasks:
        return jsonify({"error": "cannot delete category with assigned tasks"}), 409

    db.session.delete(category)
    db.session.commit()
    return jsonify({"message": "category deleted"}), 200
