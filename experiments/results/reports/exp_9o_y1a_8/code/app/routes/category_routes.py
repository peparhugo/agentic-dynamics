from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError

from app.models import db, Category
from app.schemas import CategorySchema

category_bp = Blueprint("categories", __name__)


@category_bp.route("", methods=["POST"])
@jwt_required()
def create_category():
    json_data = request.get_json(silent=True)
    if not json_data:
        return jsonify({"error": "Request body must be JSON."}), 400

    try:
        data = CategorySchema().load(json_data)
    except ValidationError as err:
        return jsonify({"error": "Validation failed.", "details": err.messages}), 400

    if Category.query.filter_by(name=data["name"]).first():
        return jsonify({"error": "Category name already exists."}), 409

    category = Category(name=data["name"], description=data.get("description"))
    db.session.add(category)
    db.session.commit()
    return jsonify(category.to_dict()), 201


@category_bp.route("", methods=["GET"])
@jwt_required()
def list_categories():
    categories = Category.query.order_by(Category.name.asc()).all()
    return jsonify([c.to_dict() for c in categories]), 200


@category_bp.route("/<category_id>", methods=["GET"])
@jwt_required()
def get_category(category_id):
    category = db.session.get(Category, category_id)
    if not category:
        return jsonify({"error": "Category not found."}), 404
    return jsonify(category.to_dict()), 200


@category_bp.route("/<category_id>", methods=["PUT"])
@jwt_required()
def update_category(category_id):
    category = db.session.get(Category, category_id)
    if not category:
        return jsonify({"error": "Category not found."}), 404

    json_data = request.get_json(silent=True)
    if not json_data:
        return jsonify({"error": "Request body must be JSON."}), 400

    try:
        data = CategorySchema().load(json_data)
    except ValidationError as err:
        return jsonify({"error": "Validation failed.", "details": err.messages}), 400

    existing = Category.query.filter(
        Category.name == data["name"], Category.id != category_id
    ).first()
    if existing:
        return jsonify({"error": "Category name already exists."}), 409

    category.name = data["name"]
    category.description = data.get("description")
    db.session.commit()
    return jsonify(category.to_dict()), 200


@category_bp.route("/<category_id>", methods=["DELETE"])
@jwt_required()
def delete_category(category_id):
    category = db.session.get(Category, category_id)
    if not category:
        return jsonify({"error": "Category not found."}), 404
    db.session.delete(category)
    db.session.commit()
    return jsonify({"message": "Category deleted."}), 200
