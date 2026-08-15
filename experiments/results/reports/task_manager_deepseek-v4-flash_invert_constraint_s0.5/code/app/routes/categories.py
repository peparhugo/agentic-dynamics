from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models import Category

categories_bp = Blueprint("categories", __name__, url_prefix="/api")


@categories_bp.post("/categories")
@jwt_required()
def create_category():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    existing = Category.query.filter_by(user_id=user_id, name=name).first()
    if existing:
        return jsonify({"error": "category already exists"}), 409

    category = Category(name=name, user_id=user_id)
    db.session.add(category)
    db.session.commit()
    return jsonify({"category": category.to_dict()}), 201


@categories_bp.get("/categories")
@jwt_required()
def list_categories():
    user_id = int(get_jwt_identity())
    categories = (
        Category.query.filter_by(user_id=user_id).order_by(Category.name.asc()).all()
    )
    return jsonify({"categories": [c.to_dict() for c in categories]})


@categories_bp.delete("/categories/<int:category_id>")
@jwt_required()
def delete_category(category_id):
    user_id = int(get_jwt_identity())
    category = db.session.get(Category, category_id)
    if category is None or category.user_id != user_id:
        return jsonify({"error": "category not found"}), 404

    db.session.delete(category)
    db.session.commit()
    return "", 204
