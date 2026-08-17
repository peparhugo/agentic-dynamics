from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.errors import APIError
from app.extensions import db
from app.models import Category, Task
from app.utils import paginate_args, paginated_response, require_fields

categories_bp = Blueprint("categories", __name__)


@categories_bp.route("", methods=["GET"])
@jwt_required()
def list_categories():
    page, per_page = paginate_args()
    query = Category.query.order_by(Category.name.asc())
    return jsonify(paginated_response(query, page, per_page))


@categories_bp.route("/<int:category_id>", methods=["GET"])
@jwt_required()
def get_category(category_id):
    category = Category.query.get(category_id)
    if not category:
        raise APIError("Category not found", 404)
    return jsonify(category.to_dict())


@categories_bp.route("", methods=["POST"])
@jwt_required()
def create_category():
    data = request.get_json(silent=True) or {}
    require_fields(data, ["name"])

    name = data["name"].strip()
    if Category.query.filter_by(name=name).first():
        raise APIError("Category with this name already exists", 409)

    category = Category(
        name=name,
        description=(data.get("description") or "").strip() or None,
        created_by=int(get_jwt_identity()),
    )
    db.session.add(category)
    db.session.commit()
    return jsonify(category.to_dict()), 201


@categories_bp.route("/<int:category_id>", methods=["PUT"])
@jwt_required()
def update_category(category_id):
    category = Category.query.get(category_id)
    if not category:
        raise APIError("Category not found", 404)

    data = request.get_json(silent=True) or {}

    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            raise APIError("name cannot be empty", 400)
        existing = Category.query.filter_by(name=name).first()
        if existing and existing.id != category.id:
            raise APIError("Category with this name already exists", 409)
        category.name = name

    if "description" in data:
        category.description = (data["description"] or "").strip() or None

    db.session.commit()
    return jsonify(category.to_dict())


@categories_bp.route("/<int:category_id>", methods=["DELETE"])
@jwt_required()
def delete_category(category_id):
    category = Category.query.get(category_id)
    if not category:
        raise APIError("Category not found", 404)

    Task.query.filter_by(category_id=category.id).update({"category_id": None})
    db.session.delete(category)
    db.session.commit()
    return "", 204
