from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from .extensions import db
from .models import Category
from .utils import error_response

categories_bp = Blueprint("categories", __name__, url_prefix="/categories")


@categories_bp.get("")
@jwt_required()
def list_categories():
    categories = Category.query.order_by(Category.name).all()
    return {"categories": [c.to_dict() for c in categories]}, 200


@categories_bp.post("")
@jwt_required()
def create_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return error_response("name is required", 400)
    if Category.query.filter_by(name=name).first():
        return error_response("category already exists", 409)

    category = Category(name=name)
    db.session.add(category)
    db.session.commit()
    return {"category": category.to_dict()}, 201


@categories_bp.get("/<int:category_id>")
@jwt_required()
def get_category(category_id):
    category = db.session.get(Category, category_id)
    if not category:
        return error_response("category not found", 404)
    return {"category": category.to_dict()}, 200


@categories_bp.delete("/<int:category_id>")
@jwt_required()
def delete_category(category_id):
    category = db.session.get(Category, category_id)
    if not category:
        return error_response("category not found", 404)
    db.session.delete(category)
    db.session.commit()
    return "", 204
