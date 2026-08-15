from flask import Blueprint, jsonify, request

from .extensions import db
from .models import Category
from .utils import admin_required, token_required

categories_bp = Blueprint("categories", __name__)


def _error(message, status=400):
    return jsonify(error=message), status


@categories_bp.get("")
@token_required
def list_categories():
    categories = Category.query.order_by(Category.name.asc()).all()
    return jsonify(
        items=[category.to_dict() for category in categories],
        total=len(categories),
    ), 200


@categories_bp.post("")
@token_required
def create_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return _error("name is required")
    if len(name) > 80:
        return _error("name must be 80 characters or fewer")

    if Category.query.filter(db.func.lower(Category.name) == name.lower()).first() is not None:
        return _error("category already exists", 409)

    description = data.get("description")
    category = Category(name=name, description=description)
    db.session.add(category)
    db.session.commit()
    return jsonify(category.to_dict()), 201


@categories_bp.get("/<int:category_id>")
@token_required
def get_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        return _error("Category not found", 404)
    return jsonify(category.to_dict()), 200


@categories_bp.put("/<int:category_id>")
@admin_required
def update_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        return _error("Category not found", 404)

    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if name is not None:
        name = str(name).strip()
        if not name:
            return _error("name must not be empty")
        if len(name) > 80:
            return _error("name must be 80 characters or fewer")
        existing = Category.query.filter(
            db.func.lower(Category.name) == name.lower(), Category.id != category.id
        ).first()
        if existing is not None:
            return _error("category already exists", 409)
        category.name = name

    if "description" in data:
        category.description = data["description"]

    db.session.commit()
    return jsonify(category.to_dict()), 200


@categories_bp.delete("/<int:category_id>")
@admin_required
def delete_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        return _error("Category not found", 404)

    Task = db.Model.metadata.tables["tasks"]
    db.session.execute(
        Task.update().where(Task.c.category_id == category_id).values(category_id=None)
    )
    db.session.delete(category)
    db.session.commit()
    return "", 204
