from datetime import date, datetime, timezone
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from .db import get_db


STATUSES = ("pending", "in_progress", "completed")
PRIORITIES = ("low", "medium", "high", "urgent")


def error(message, status=400):
    return jsonify(error=message), status


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, error("request body must be a JSON object")
    return data, None


def auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return error("missing or invalid authorization header", 401)
        try:
            payload = jwt.decode(
                header[7:], current_app.config["JWT_SECRET"], algorithms=["HS256"]
            )
            user = get_db().execute(
                "SELECT id, username, email FROM users WHERE id = ?", (int(payload["sub"]),)
            ).fetchone()
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            return error("invalid or expired token", 401)
        if user is None:
            return error("invalid or expired token", 401)
        g.user = user
        return view(*args, **kwargs)

    return wrapped


def normalize_due_date(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("due_date must be an ISO 8601 date or datetime")
    try:
        if "T" in value:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError("due_date must be an ISO 8601 date or datetime") from exc


def serialize_task(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "priority": row["priority"],
        "due_date": row["due_date"],
        "category": (
            {"id": row["category_id"], "name": row["category_name"]}
            if row["category_id"] is not None
            else None
        ),
        "creator_id": row["creator_id"],
        "assignee": (
            {"id": row["assignee_id"], "username": row["assignee_name"]}
            if row["assignee_id"] is not None
            else None
        ),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


TASK_SELECT = """
SELECT t.*, c.name AS category_name, u.username AS assignee_name
FROM tasks t
LEFT JOIN categories c ON c.id = t.category_id
LEFT JOIN users u ON u.id = t.assignee_id
"""
