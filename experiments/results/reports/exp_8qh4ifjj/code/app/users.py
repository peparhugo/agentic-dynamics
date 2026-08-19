from flask import Blueprint, jsonify

from .auth import token_required
from .db import get_db

bp = Blueprint("users", __name__)

VALID_STATUSES = ("pending", "in_progress", "completed")
VALID_PRIORITIES = ("low", "medium", "high")


def _task_row_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "priority": row["priority"],
        "category_id": row["category_id"],
        "category": row["category"],
        "due_date": row["due_date"],
        "created_by": row["created_by"],
        "assigned_to": row["assigned_to"],
        "assigned_username": row["assigned_username"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


TASK_SELECT = """
    SELECT t.*, c.name AS category, u.username AS assigned_username
    FROM tasks t
    LEFT JOIN categories c ON c.id = t.category_id
    LEFT JOIN users u ON u.id = t.assigned_to
"""


@bp.get("/users")
@token_required
def list_users():
    rows = get_db().execute(
        "SELECT id, username, created_at FROM users ORDER BY username"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.get("/categories")
@token_required
def list_categories():
    rows = get_db().execute("SELECT * FROM categories ORDER BY name").fetchall()
    return jsonify([dict(r) for r in rows])


@bp.post("/categories")
@token_required
def create_category():
    from flask import request

    from .errors import ApiError

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        raise ApiError("name is required", 400)

    db = get_db()
    existing = db.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
    if existing:
        raise ApiError("Category already exists", 409)
    cur = db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
    db.commit()
    row = db.execute("SELECT * FROM categories WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201
