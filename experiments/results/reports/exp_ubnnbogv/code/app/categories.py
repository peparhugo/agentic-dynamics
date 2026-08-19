from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from .auth import login_required
from .db import db
from .errors import ApiError
from .models import Category, Task

bp = Blueprint("categories", __name__, url_prefix="/api")


@bp.get("/categories")
@login_required
def list_categories():
    categories = Category.query.order_by(Category.name.asc()).all()
    return jsonify({"items": [category.to_dict() for category in categories], "total": len(categories)})


@bp.post("/categories")
@login_required
def create_category():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        raise ApiError("invalid JSON body", 400)
    name = (data.get("name") or "").strip()
    if not name:
        raise ApiError("name is required", 400, {"name": "required"})
    if Category.query.filter_by(name=name).first():
        raise ApiError("category already exists", 409, {"name": "exists"})

    category = Category(name=name)
    db.session.add(category)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError("category already exists", 409)
    return jsonify(category.to_dict()), 201


@bp.delete("/categories/<int:category_id>")
@login_required
def delete_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        raise ApiError("category not found", 404)
    Task.query.filter_by(category_id=category.id).update({"category_id": None}, synchronize_session=False)
    db.session.delete(category)
    db.session.commit()
    return "", 204
