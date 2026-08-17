from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from .db import get_db

bp = Blueprint("priorities", __name__, url_prefix="/priorities")


@bp.get("")
@jwt_required()
def list_priorities():
    db = get_db()
    rows = db.execute(
        """
        SELECT p.*, (SELECT COUNT(*) FROM tasks t WHERE t.priority_id = p.id) AS task_count
        FROM priorities p
        ORDER BY p.level
        """
    ).fetchall()
    return jsonify(
        {
            "items": [
                {"id": r["id"], "name": r["name"], "level": r["level"], "task_count": r["task_count"]}
                for r in rows
            ]
        }
    )
