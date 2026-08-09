"""Category CRUD. Categories are scoped per user."""
from flask import Blueprint, g, jsonify, request

from .auth import require_auth
from .db import get_db
from .errors import APIError

bp = Blueprint("categories", __name__, url_prefix="/api/categories")

MAX_NAME_LEN = 64


def category_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "user_id": row["user_id"],
        "created_at": row["created_at"],
    }


def _get_owned_category(category_id: int):
    row = get_db().execute(
        "SELECT * FROM categories WHERE id = ? AND user_id = ?",
        (category_id, g.current_user["id"]),
    ).fetchone()
    if row is None:
        raise APIError("Category not found", 404)
    return row


def _validated_name(data) -> str:
    if not isinstance(data, dict):
        raise APIError("Request body must be a JSON object", 400)
    name = str(data.get("name", "")).strip()
    if not name or len(name) > MAX_NAME_LEN:
        raise APIError(f"name is required (1-{MAX_NAME_LEN} chars)", 400)
    return name


@bp.get("")
@require_auth
def list_categories():
    rows = get_db().execute(
        "SELECT * FROM categories WHERE user_id = ? ORDER BY name",
        (g.current_user["id"],),
    ).fetchall()
    return jsonify({"categories": [category_to_dict(r) for r in rows]})


@bp.post("")
@require_auth
def create_category():
    name = _validated_name(request.get_json(silent=True))
    db = get_db()
    dup = db.execute(
        "SELECT 1 FROM categories WHERE name = ? AND user_id = ?",
        (name, g.current_user["id"]),
    ).fetchone()
    if dup:
        raise APIError("Category with this name already exists", 409)
    cur = db.execute(
        "INSERT INTO categories (name, user_id) VALUES (?, ?)",
        (name, g.current_user["id"]),
    )
    db.commit()
    row = db.execute("SELECT * FROM categories WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify({"category": category_to_dict(row)}), 201


@bp.get("/<int:category_id>")
@require_auth
def get_category(category_id):
    return jsonify({"category": category_to_dict(_get_owned_category(category_id))})


@bp.put("/<int:category_id>")
@require_auth
def update_category(category_id):
    _get_owned_category(category_id)
    name = _validated_name(request.get_json(silent=True))
    db = get_db()
    dup = db.execute(
        "SELECT 1 FROM categories WHERE name = ? AND user_id = ? AND id != ?",
        (name, g.current_user["id"], category_id),
    ).fetchone()
    if dup:
        raise APIError("Category with this name already exists", 409)
    db.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
    db.commit()
    return jsonify({"category": category_to_dict(_get_owned_category(category_id))})


@bp.delete("/<int:category_id>")
@require_auth
def delete_category(category_id):
    _get_owned_category(category_id)
    db = get_db()
    db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    db.commit()
    return "", 204
