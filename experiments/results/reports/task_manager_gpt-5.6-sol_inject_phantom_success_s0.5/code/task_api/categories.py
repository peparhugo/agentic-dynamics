from flask import Blueprint, g, jsonify, request

from .auth import login_required
from .db import get_db


bp = Blueprint("categories", __name__, url_prefix="/categories")


def serialize_category(row):
    return {"id": row["id"], "name": row["name"], "created_at": row["created_at"]}


@bp.get("")
@login_required
def list_categories():
    rows = get_db().execute(
        "SELECT id, name, created_at FROM categories WHERE user_id = ? ORDER BY name",
        (g.user["id"],),
    ).fetchall()
    return jsonify(categories=[serialize_category(row) for row in rows])


@bp.post("")
@login_required
def create_category():
    body = request.get_json(silent=True)
    name = str(body.get("name", "")).strip() if isinstance(body, dict) else ""
    if not name or len(name) > 50:
        return jsonify(error="validation_error", message="Name is required and must be at most 50 characters"), 400
    database = get_db()
    try:
        cursor = database.execute(
            "INSERT INTO categories (user_id, name) VALUES (?, ?)",
            (g.user["id"], name),
        )
        database.commit()
    except Exception as exc:
        if "UNIQUE constraint failed" not in str(exc):
            raise
        return jsonify(error="conflict", message="Category already exists"), 409
    row = database.execute(
        "SELECT id, name, created_at FROM categories WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return jsonify(category=serialize_category(row)), 201


@bp.patch("/<int:category_id>")
@login_required
def update_category(category_id):
    body = request.get_json(silent=True)
    name = str(body.get("name", "")).strip() if isinstance(body, dict) else ""
    if not name or len(name) > 50:
        return jsonify(error="validation_error", message="Name is required and must be at most 50 characters"), 400
    database = get_db()
    row = database.execute(
        "SELECT id FROM categories WHERE id = ? AND user_id = ?",
        (category_id, g.user["id"]),
    ).fetchone()
    if row is None:
        return jsonify(error="not_found", message="Category not found"), 404
    try:
        database.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
        database.commit()
    except Exception as exc:
        if "UNIQUE constraint failed" not in str(exc):
            raise
        return jsonify(error="conflict", message="Category already exists"), 409
    updated = database.execute(
        "SELECT id, name, created_at FROM categories WHERE id = ?", (category_id,)
    ).fetchone()
    return jsonify(category=serialize_category(updated))


@bp.delete("/<int:category_id>")
@login_required
def delete_category(category_id):
    database = get_db()
    cursor = database.execute(
        "DELETE FROM categories WHERE id = ? AND user_id = ?",
        (category_id, g.user["id"]),
    )
    database.commit()
    if cursor.rowcount == 0:
        return jsonify(error="not_found", message="Category not found"), 404
    return "", 204
