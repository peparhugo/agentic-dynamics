from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..models import db, Category, User

categories_bp = Blueprint("categories", __name__, url_prefix="/api/categories")


@categories_bp.route("", methods=["GET"])
def list_categories():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)

    pagination = Category.query.order_by(Category.name).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "categories": [c.to_dict() for c in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }), 200


@categories_bp.route("/<int:category_id>", methods=["GET"])
def get_category(category_id):
    category = db.session.get(Category, category_id)
    if not category:
        return jsonify({"error": "Category not found"}), 404
    return jsonify({"category": category.to_dict()}), 200


@categories_bp.route("", methods=["POST"])
@jwt_required()
def create_category():
    data = request.get_json()
    if "name" not in data:
        return jsonify({"error": "Name is required"}), 400

    if Category.query.filter_by(name=data["name"]).first():
        return jsonify({"error": "Category already exists"}), 409

    category = Category(name=data["name"], description=data.get("description"))
    db.session.add(category)
    db.session.commit()

    return jsonify({"category": category.to_dict()}), 201


@categories_bp.route("/<int:category_id>", methods=["PUT"])
@jwt_required()
def update_category(category_id):
    category = db.session.get(Category, category_id)
    if not category:
        return jsonify({"error": "Category not found"}), 404

    data = request.get_json()
    if "name" in data:
        existing = Category.query.filter(
            Category.name == data["name"], Category.id != category_id
        ).first()
        if existing:
            return jsonify({"error": "Category name already taken"}), 409
        category.name = data["name"]
    if "description" in data:
        category.description = data["description"]

    db.session.commit()
    return jsonify({"category": category.to_dict()}), 200


@categories_bp.route("/<int:category_id>", methods=["DELETE"])
@jwt_required()
def delete_category(category_id):
    category = db.session.get(Category, category_id)
    if not category:
        return jsonify({"error": "Category not found"}), 404
    db.session.delete(category)
    db.session.commit()
    return jsonify({"message": "Category deleted"}), 200
