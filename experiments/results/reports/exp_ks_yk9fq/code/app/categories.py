from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import Category
from app.utils import token_required

categories_bp = Blueprint("categories", __name__)


@categories_bp.route("/categories", methods=["GET"])
@token_required
def list_categories():
    categories = Category.query.order_by(Category.name.asc()).all()
    return jsonify({"categories": [c.to_dict() for c in categories]}), 200


@categories_bp.route("/categories", methods=["POST"])
@token_required
def create_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    color = (data.get("color") or "").strip() or None

    if not name:
        return jsonify({"error": "Category name is required"}), 400

    if Category.query.filter_by(name=name).first():
        return jsonify({"error": "Category already exists"}), 409

    category = Category(name=name, color=color)
    db.session.add(category)
    db.session.commit()
    return jsonify({"message": "Category created", "category": category.to_dict()}), 201


@categories_bp.route("/categories/<int:category_id>", methods=["GET"])
@token_required
def get_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        return jsonify({"error": "Category not found"}), 404
    return jsonify({"category": category.to_dict()}), 200


@categories_bp.route("/categories/<int:category_id>", methods=["PUT"])
@token_required
def update_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        return jsonify({"error": "Category not found"}), 404

    data = request.get_json(silent=True) or {}
    name = data.get("name")
    color = data.get("color")

    if name is not None:
        name = name.strip()
        if not name:
            return jsonify({"error": "Category name cannot be empty"}), 400
        existing = Category.query.filter(
            Category.name == name, Category.id != category_id
        ).first()
        if existing:
            return jsonify({"error": "Category already exists"}), 409
        category.name = name

    if color is not None:
        category.color = color.strip() or None

    db.session.commit()
    return jsonify({"message": "Category updated", "category": category.to_dict()}), 200


@categories_bp.route("/categories/<int:category_id>", methods=["DELETE"])
@token_required
def delete_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        return jsonify({"error": "Category not found"}), 404

    tasks = category.tasks.count()
    if tasks:
        return jsonify(
            {"error": "Cannot delete category with associated tasks", "task_count": tasks}
        ), 409

    db.session.delete(category)
    db.session.commit()
    return jsonify({"message": "Category deleted"}), 200
