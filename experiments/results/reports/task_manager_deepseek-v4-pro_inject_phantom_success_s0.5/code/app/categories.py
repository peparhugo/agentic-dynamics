from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import Category

category_bp = Blueprint("categories", __name__, url_prefix="/api/categories")


def _category_to_dict(category):
    return {
        "id": category.id,
        "name": category.name,
        "description": category.description,
        "created_at": category.created_at.isoformat() if category.created_at else None,
    }


@category_bp.route("", methods=["GET"])
@jwt_required()
def list_categories():
    categories = Category.query.order_by(Category.name).all()
    return jsonify({"categories": [_category_to_dict(c) for c in categories]}), 200


@category_bp.route("", methods=["POST"])
@jwt_required()
def create_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip() or None

    if not name:
        return jsonify({"message": "name is required"}), 400

    if Category.query.filter_by(name=name).first():
        return jsonify({"message": "category already exists"}), 409

    category = Category(name=name, description=description)
    db.session.add(category)
    db.session.commit()
    return jsonify(_category_to_dict(category)), 201


@category_bp.route("/<int:category_id>", methods=["GET"])
@jwt_required()
def get_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        return jsonify({"message": "category not found"}), 404
    return jsonify(_category_to_dict(category)), 200


@category_bp.route("/<int:category_id>", methods=["PUT"])
@jwt_required()
def update_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        return jsonify({"message": "category not found"}), 404

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()

    if name:
        existing = Category.query.filter(Category.name == name, Category.id != category_id).first()
        if existing:
            return jsonify({"message": "category already exists"}), 409
        category.name = name
    if "description" in data:
        category.description = description or None

    db.session.commit()
    return jsonify(_category_to_dict(category)), 200


@category_bp.route("/<int:category_id>", methods=["DELETE"])
@jwt_required()
def delete_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        return jsonify({"message": "category not found"}), 404

    # Detach tasks from this category
    from app.models import Task

    Task.query.filter_by(category_id=category_id).update({"category_id": None})
    db.session.delete(category)
    db.session.commit()
    return jsonify({"message": "category deleted"}), 200
