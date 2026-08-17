from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models import Category, Task

categories_bp = Blueprint("categories", __name__)


@categories_bp.get("")
@jwt_required()
def list_categories():
    user_id = int(get_jwt_identity())
    categories = (
        Category.query.filter_by(owner_id=user_id).order_by(Category.name).all()
    )
    return jsonify({"categories": [c.to_dict() for c in categories]}), 200


@categories_bp.post("")
@jwt_required()
def create_category():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    description = data.get("description")

    if not name:
        return jsonify({"error": "Category name is required"}), 400

    if Category.query.filter_by(owner_id=user_id, name=name).first():
        return jsonify({"error": "Category already exists"}), 409

    category = Category(name=name, description=description, owner_id=user_id)
    db.session.add(category)
    db.session.commit()

    return jsonify({"category": category.to_dict()}), 201


@categories_bp.get("/<int:category_id>")
@jwt_required()
def get_category(category_id):
    user_id = int(get_jwt_identity())
    category = Category.query.get_or_404(category_id)
    if category.owner_id != user_id:
        return jsonify({"error": "Forbidden"}), 403
    return jsonify({"category": category.to_dict()}), 200


@categories_bp.put("/<int:category_id>")
@jwt_required()
def update_category(category_id):
    user_id = int(get_jwt_identity())
    category = Category.query.get_or_404(category_id)
    if category.owner_id != user_id:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if name is not None:
        name = name.strip()
        if not name:
            return jsonify({"error": "Category name cannot be empty"}), 400
        existing = Category.query.filter_by(owner_id=user_id, name=name).first()
        if existing and existing.id != category.id:
            return jsonify({"error": "Category already exists"}), 409
        category.name = name
    if "description" in data:
        category.description = data.get("description")

    db.session.commit()
    return jsonify({"category": category.to_dict()}), 200


@categories_bp.delete("/<int:category_id>")
@jwt_required()
def delete_category(category_id):
    user_id = int(get_jwt_identity())
    category = Category.query.get_or_404(category_id)
    if category.owner_id != user_id:
        return jsonify({"error": "Forbidden"}), 403

    Task.query.filter_by(category_id=category.id).update({"category_id": None})
    db.session.delete(category)
    db.session.commit()
    return jsonify({"message": "Category deleted"}), 200
