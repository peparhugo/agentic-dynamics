from flask import Blueprint, jsonify, request, g

from app.auth import auth_required
from app.db import get_db, row_to_dict

categories_bp = Blueprint("categories", __name__, url_prefix="/categories")

VALID_STATUSES = ("todo", "in_progress", "done")
VALID_PRIORITIES = ("low", "medium", "high")


@categories_bp.post("")
@auth_required
def create_category():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO categories (name, user_id) VALUES (?, ?)", (name, g.user["id"])
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 - surfaces UNIQUE constraint
        if "UNIQUE" in str(exc):
            return jsonify({"error": "category already exists"}), 409
        raise
    return (
        jsonify({"category": row_to_dict(db.execute("SELECT * FROM categories WHERE id = ?", (cursor.lastrowid,)).fetchone())}),
        201,
    )


@categories_bp.get("")
@auth_required
def list_categories():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM categories WHERE user_id = ? ORDER BY name", (g.user["id"],)
    ).fetchall()
    return jsonify({"categories": [row_to_dict(r) for r in rows]}), 200


@categories_bp.get("/<int:category_id>")
@auth_required
def get_category(category_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM categories WHERE id = ? AND user_id = ?", (category_id, g.user["id"])
    ).fetchone()
    if row is None:
        return jsonify({"error": "category not found"}), 404
    return jsonify({"category": row_to_dict(row)}), 200


@categories_bp.delete("/<int:category_id>")
@auth_required
def delete_category(category_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM categories WHERE id = ? AND user_id = ?", (category_id, g.user["id"])
    ).fetchone()
    if row is None:
        return jsonify({"error": "category not found"}), 404
    db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    db.commit()
    return jsonify({"message": "category deleted"}), 200


@categories_bp.patch("/<int:category_id>")
@auth_required
def update_category(category_id):
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    db = get_db()
    row = db.execute(
        "SELECT * FROM categories WHERE id = ? AND user_id = ?", (category_id, g.user["id"])
    ).fetchone()
    if row is None:
        return jsonify({"error": "category not found"}), 404
    try:
        db.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
        db.commit()
    except Exception as exc:  # noqa: BLE001 - surfaces UNIQUE constraint
        if "UNIQUE" in str(exc):
            return jsonify({"error": "category already exists"}), 409
        raise
    return (
        jsonify({"category": row_to_dict(db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone())}),
        200,
    )
