from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models import Category, Task
from app.utils import error_response, paginate_query

categories_bp = Blueprint("categories", __name__)


@categories_bp.post("")
@jwt_required()
def create_category():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()

    if not name:
        return error_response("Category name is required", 422, {"name": "This field is required"})

    if Category.query.filter_by(name=name, owner_id=user_id).first():
        return error_response("Category with this name already exists", 409)

    category = Category(name=name, owner_id=user_id)
    db.session.add(category)
    db.session.commit()
    return jsonify(category.to_dict()), 201


@categories_bp.get("")
@jwt_required()
def list_categories():
    user_id = int(get_jwt_identity())
    query = Category.query.filter_by(owner_id=user_id).order_by(Category.name.asc())
    result = paginate_query(query, lambda c: c.to_dict())
    return jsonify(result), 200


@categories_bp.get("/<int:category_id>")
@jwt_required()
def get_category(category_id):
    user_id = int(get_jwt_identity())
    category = Category.query.filter_by(id=category_id, owner_id=user_id).first()
    if not category:
        return error_response("Category not found", 404)
    return jsonify(category.to_dict()), 200


@categories_bp.put("/<int:category_id>")
@jwt_required()
def update_category(category_id):
    user_id = int(get_jwt_identity())
    category = Category.query.filter_by(id=category_id, owner_id=user_id).first()
    if not category:
        return error_response("Category not found", 404)

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return error_response("Category name is required", 422, {"name": "This field is required"})

    existing = Category.query.filter_by(name=name, owner_id=user_id).first()
    if existing and existing.id != category.id:
        return error_response("Category with this name already exists", 409)

    category.name = name
    db.session.commit()
    return jsonify(category.to_dict()), 200


@categories_bp.delete("/<int:category_id>")
@jwt_required()
def delete_category(category_id):
    user_id = int(get_jwt_identity())
    category = Category.query.filter_by(id=category_id, owner_id=user_id).first()
    if not category:
        return error_response("Category not found", 404)

    Task.query.filter_by(category_id=category.id).update({"category_id": None})
    db.session.delete(category)
    db.session.commit()
    return "", 204
