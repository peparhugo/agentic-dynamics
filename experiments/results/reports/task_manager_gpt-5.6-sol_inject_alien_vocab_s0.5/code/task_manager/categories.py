from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from task_manager import db
from task_manager.models import Category
from task_manager.utils import json_body, json_error


categories_bp = Blueprint("categories", __name__)


@categories_bp.get("")
@jwt_required()
def list_categories():
    categories = Category.query.order_by(Category.name.asc()).all()
    return jsonify(categories=[category.to_dict() for category in categories])


@categories_bp.post("")
@jwt_required()
def create_category():
    data = json_body()
    if not isinstance(data, dict):
        return json_error("A JSON object is required")
    name = data.get("name", "").strip() if isinstance(data.get("name", ""), str) else ""
    description = data.get("description")
    if not name:
        return json_error("name is required")
    if len(name) > 80:
        return json_error("name must not exceed 80 characters")
    if description is not None and not isinstance(description, str):
        return json_error("description must be a string or null")
    if Category.query.filter(db.func.lower(Category.name) == name.lower()).first():
        return json_error("category name already exists", 409)
    category = Category(name=name, description=description)
    db.session.add(category)
    db.session.commit()
    return jsonify(category=category.to_dict()), 201


@categories_bp.patch("/<int:category_id>")
@jwt_required()
def update_category(category_id):
    category = db.get_or_404(Category, category_id)
    data = json_body()
    if not isinstance(data, dict):
        return json_error("A JSON object is required")
    if "name" in data:
        if not isinstance(data["name"], str) or not data["name"].strip():
            return json_error("name must be a non-empty string")
        name = data["name"].strip()
        duplicate = Category.query.filter(
            db.func.lower(Category.name) == name.lower(), Category.id != category.id
        ).first()
        if duplicate:
            return json_error("category name already exists", 409)
        category.name = name
    if "description" in data:
        if data["description"] is not None and not isinstance(data["description"], str):
            return json_error("description must be a string or null")
        category.description = data["description"]
    db.session.commit()
    return jsonify(category=category.to_dict())


@categories_bp.delete("/<int:category_id>")
@jwt_required()
def delete_category(category_id):
    category = db.get_or_404(Category, category_id)
    if category.tasks:
        return json_error("Cannot delete a category used by tasks", 409)
    db.session.delete(category)
    db.session.commit()
    return "", 204
