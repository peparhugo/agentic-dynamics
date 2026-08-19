from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from .db import get_db

bp = Blueprint("categories", __name__, url_prefix="/categories")


@bp.get("")
@jwt_required()
def list_categories():
    db = get_db()
    rows = db.execute(
        """
        SELECT c.*, (SELECT COUNT(*) FROM tasks t WHERE t.category_id = c.id) AS task_count
        FROM categories c
        ORDER BY c.name
        """
    ).fetchall()
    return jsonify(
        {
            "items": [
                {"id": r["id"], "name": r["name"], "created_at": r["created_at"], "task_count": r["task_count"]}
                for r in rows
            ]
        }
    )


@bp.post("")
@jwt_required()
def create_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return {"error": "name is required"}, 400
    db = get_db()
    if db.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone():
        return {"error": f"category '{name}' already exists"}, 409
    cur = db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
    db.commit()
    row = db.execute("SELECT * FROM categories WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(
        {"id": row["id"], "name": row["name"], "created_at": row["created_at"], "task_count": 0}
    ), 201
