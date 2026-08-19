from flask import Blueprint, jsonify, request

from .extensions import db
from .models import Category
from .utils import login_required

bp = Blueprint("categories", __name__, url_prefix="/api/categories")


@bp.get("")
@login_required
def list_categories():
    categories = Category.query.order_by(Category.name.asc()).all()
    return jsonify({"categories": [c.to_dict() for c in categories]}), 200


@bp.post("")
@login_required
def create_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    color = (data.get("color") or "").strip() or None

    if not name:
        return jsonify({"error": "Name is required."}), 400
    if len(name) > 80:
        return jsonify({"error": "Name must be 80 characters or fewer."}), 400
    if color and len(color) > 20:
        return jsonify({"error": "Color must be 20 characters or fewer."}), 400

    if Category.query.filter_by(name=name).first():
        return jsonify({"error": "Category already exists."}), 409

    category = Category(name=name, color=color)
    db.session.add(category)
    db.session.commit()
    return jsonify({"category": category.to_dict()}), 201


@bp.delete("/<int:category_id>")
@login_required
def delete_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        return jsonify({"error": "Category not found."}), 404

    if category.tasks.count() > 0:
        return (
            jsonify(
                {"error": "Cannot delete a category that is still assigned to tasks."}
            ),
            409,
        )

    db.session.delete(category)
    db.session.commit()
    return jsonify({"message": "Category deleted."}), 200
