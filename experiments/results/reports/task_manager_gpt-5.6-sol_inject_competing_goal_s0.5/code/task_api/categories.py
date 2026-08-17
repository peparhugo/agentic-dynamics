import sqlite3

from flask import Blueprint, g, jsonify

from .common import auth_required, error, json_body
from .db import get_db


categories_bp = Blueprint("categories", __name__)


def serialized(row):
    return {"id": row["id"], "name": row["name"], "created_at": row["created_at"]}


@categories_bp.get("")
@auth_required
def list_categories():
    rows = get_db().execute(
        "SELECT * FROM categories WHERE user_id = ? ORDER BY name", (g.user["id"],)
    ).fetchall()
    return jsonify(items=[serialized(row) for row in rows])


@categories_bp.post("")
@auth_required
def create_category():
    data, response = json_body()
    if response:
        return response
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return error("name is required")
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO categories(user_id, name) VALUES (?, ?)", (g.user["id"], name.strip())
        )
        db.commit()
    except sqlite3.IntegrityError:
        return error("category already exists", 409)
    row = db.execute("SELECT * FROM categories WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(serialized(row)), 201


@categories_bp.patch("/<int:category_id>")
@auth_required
def update_category(category_id):
    data, response = json_body()
    if response:
        return response
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return error("name is required")
    db = get_db()
    try:
        cursor = db.execute(
            "UPDATE categories SET name = ? WHERE id = ? AND user_id = ?",
            (name.strip(), category_id, g.user["id"]),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return error("category already exists", 409)
    if cursor.rowcount == 0:
        return error("category not found", 404)
    row = db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    return jsonify(serialized(row))


@categories_bp.delete("/<int:category_id>")
@auth_required
def delete_category(category_id):
    db = get_db()
    cursor = db.execute(
        "DELETE FROM categories WHERE id = ? AND user_id = ?", (category_id, g.user["id"])
    )
    db.commit()
    if cursor.rowcount == 0:
        return error("category not found", 404)
    return "", 204
