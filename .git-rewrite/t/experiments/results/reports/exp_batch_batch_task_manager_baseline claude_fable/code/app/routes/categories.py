"""Category CRUD endpoints (scoped to the authenticated user)."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.models import Category

categories_bp = Blueprint("categories", __name__)


def _current_user_id() -> int:
    return int(get_jwt_identity())


@categories_bp.post("")
@jwt_required()
def create_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    if len(name) > 80:
        return jsonify({"error": "name must be at most 80 characters"}), 400

    user_id = _current_user_id()
    if Category.query.filter_by(name=name, user_id=user_id).first():
        return jsonify({"error": "Category already exists"}), 409

    category = Category(name=name,
                        description=(data.get("description") or "").strip(),
                        user_id=user_id)
    db.session.add(category)
    db.session.commit()
    return jsonify({"category": category.to_dict()}), 201


@categories_bp.get("")
@jwt_required()
def list_categories():
    categories = (Category.query
                  .filter_by(user_id=_current_user_id())
                  .order_by(Category.name.asc())
                  .all())
    return jsonify({"categories": [c.to_dict() for c in categories]}), 200


@categories_bp.get("/<int:category_id>")
@jwt_required()
def get_category(category_id: int):
    category = Category.query.filter_by(
        id=category_id, user_id=_current_user_id()).first()
    if not category:
        return jsonify({"error": "Category not found"}), 404
    return jsonify({"category": category.to_dict()}), 200


@categories_bp.put("/<int:category_id>")
@jwt_required()
def update_category(category_id: int):
    user_id = _current_user_id()
    category = Category.query.filter_by(id=category_id, user_id=user_id).first()
    if not category:
        return jsonify({"error": "Category not found"}), 404

    data = request.get_json(silent=True) or {}
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "name cannot be empty"}), 400
        existing = Category.query.filter(
            Category.name == name,
            Category.user_id == user_id,
            Category.id != category_id).first()
        if existing:
            return jsonify({"error": "Category already exists"}), 409
        category.name = name
    if "description" in data:
        category.description = (data.get("description") or "").strip()

    db.session.commit()
    return jsonify({"category": category.to_dict()}), 200


@categories_bp.delete("/<int:category_id>")
@jwt_required()
def delete_category(category_id: int):
    category = Category.query.filter_by(
        id=category_id, user_id=_current_user_id()).first()
    if not category:
        return jsonify({"error": "Category not found"}), 404

    # Detach tasks from the deleted category.
    for task in category.tasks:
        task.category_id = None

    db.session.delete(category)
    db.session.commit()
    return jsonify({"message": "Category deleted"}), 200
