from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Category

categories_bp = Blueprint("categories", __name__)


@categories_bp.route("", methods=["GET"])
@jwt_required()
def list_categories():
    categories = Category.query.order_by(Category.name.asc()).all()
    return jsonify({"items": [c.to_dict() for c in categories]}), 200


@categories_bp.route("", methods=["POST"])
@jwt_required()
def create_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    category = Category(name=name)
    db.session.add(category)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "category already exists"}), 409

    return jsonify({"category": category.to_dict()}), 201


@categories_bp.route("/<int:category_id>", methods=["GET"])
@jwt_required()
def get_category(category_id):
    category = db.session.get(Category, category_id)
    if not category:
        return jsonify({"error": "category not found"}), 404
    return jsonify({"category": category.to_dict()}), 200


@categories_bp.route("/<int:category_id>", methods=["DELETE"])
@jwt_required()
def delete_category(category_id):
    category = db.session.get(Category, category_id)
    if not category:
        return jsonify({"error": "category not found"}), 404
    db.session.delete(category)
    db.session.commit()
    return "", 204
