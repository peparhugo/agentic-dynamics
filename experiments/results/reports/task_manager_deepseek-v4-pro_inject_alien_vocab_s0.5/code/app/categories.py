from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from .extensions import db
from .models import Category

categories_bp = Blueprint("categories", __name__, url_prefix="/api/categories")


@categories_bp.route("", methods=["GET"])
@jwt_required()
def list_categories():
    categories = Category.query.order_by(Category.name.asc()).all()
    return jsonify({"categories": [c.to_dict() for c in categories]}), 200


@categories_bp.route("", methods=["POST"])
@jwt_required()
def create_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    color = data.get("color")

    if not name:
        return jsonify({"message": "Name is required."}), 400

    if Category.query.filter_by(name=name).first():
        return jsonify({"message": "Category already exists."}), 409

    category = Category(name=name, color=color)
    db.session.add(category)
    db.session.commit()

    return jsonify({"category": category.to_dict()}), 201
