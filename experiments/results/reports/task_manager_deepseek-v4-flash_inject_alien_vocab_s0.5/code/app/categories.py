from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.db import get_db

bp = Blueprint("categories", __name__, url_prefix="/categories")


def _public_category(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "created_at": row["created_at"],
    }


def _find_category(category_id):
    return get_db().execute(
        "SELECT * FROM categories WHERE id = ?", (category_id,)
    ).fetchone()


@bp.get("")
@jwt_required()
def list_categories():
    rows = get_db().execute(
        "SELECT * FROM categories ORDER BY name COLLATE NOCASE ASC"
    ).fetchall()
    return jsonify({"categories": [_public_category(r) for r in rows]}), 200


@bp.post("")
@jwt_required()
def create_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    db = get_db()
    existing = db.execute(
        "SELECT id FROM categories WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()
    if existing:
        return jsonify({"error": "category already exists"}), 409

    cursor = db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
    db.commit()
    return jsonify(_public_category(_find_category(cursor.lastrowid))), 201


@bp.get("/<int:category_id>")
@jwt_required()
def get_category(category_id):
    row = _find_category(category_id)
    if row is None:
        return jsonify({"error": "category not found"}), 404
    return jsonify(_public_category(row)), 200


@bp.delete("/<int:category_id>")
@jwt_required()
def delete_category(category_id):
    db = get_db()
    row = _find_category(category_id)
    if row is None:
        return jsonify({"error": "category not found"}), 404
    db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    db.commit()
    return jsonify({"message": "category deleted"}), 200
