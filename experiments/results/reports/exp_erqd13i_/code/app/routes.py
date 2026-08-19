"""HTTP endpoints for task resources."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from .db import get_db

tasks = Blueprint("tasks", __name__, url_prefix="/tasks")

ALLOWED_FIELDS = {"title", "description", "status", "due_date"}
ALLOWED_STATUSES = {"pending", "in_progress", "completed"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _task_dict(task: sqlite3.Row) -> dict:
    return dict(task)


def _error(message: str, status: int = 400) -> tuple[object, int]:
    return jsonify({"error": message}), status


def _json_body() -> tuple[dict | None, tuple[object, int] | None]:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return None, _error("Request body must be a JSON object")
    unknown = set(body) - ALLOWED_FIELDS
    if unknown:
        return None, _error(f"Unknown field(s): {', '.join(sorted(unknown))}")
    return body, None


def _validate(data: dict, *, creating: bool) -> str | None:
    if creating and "title" not in data:
        return "title is required"
    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
        return "title must be a non-empty string"
    if "description" in data and data["description"] is not None and not isinstance(data["description"], str):
        return "description must be a string or null"
    if "status" in data and data["status"] not in ALLOWED_STATUSES:
        return "status must be one of: pending, in_progress, completed"
    if "due_date" in data:
        due_date = data["due_date"]
        if due_date is not None and (not isinstance(due_date, str) or not _is_date(due_date)):
            return "due_date must be an ISO-8601 date (YYYY-MM-DD) or null"
    return None


def _is_date(value: str) -> bool:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") == value
    except ValueError:
        return False


@tasks.get("")
def list_tasks() -> tuple[object, int]:
    status = request.args.get("status")
    if status is not None and status not in ALLOWED_STATUSES:
        return _error("status must be one of: pending, in_progress, completed")
    db = get_db()
    query = "SELECT * FROM tasks"
    parameters: tuple[str, ...] = ()
    if status:
        query += " WHERE status = ?"
        parameters = (status,)
    query += " ORDER BY id"
    return jsonify([_task_dict(row) for row in db.execute(query, parameters)]), 200


@tasks.post("")
def create_task() -> tuple[object, int]:
    data, error = _json_body()
    if error:
        return error
    assert data is not None
    validation_error = _validate(data, creating=True)
    if validation_error:
        return _error(validation_error)
    now = _now()
    db = get_db()
    cursor = db.execute(
        """INSERT INTO tasks (title, description, status, due_date, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (data["title"].strip(), data.get("description"), data.get("status", "pending"), data.get("due_date"), now, now),
    )
    db.commit()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(_task_dict(task)), 201


@tasks.get("/<int:task_id>")
def get_task(task_id: int) -> tuple[object, int]:
    task = get_db().execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if task is None:
        return _error("Task not found", 404)
    return jsonify(_task_dict(task)), 200


@tasks.patch("/<int:task_id>")
def update_task(task_id: int) -> tuple[object, int]:
    data, error = _json_body()
    if error:
        return error
    assert data is not None
    if not data:
        return _error("Request body must include at least one updatable field")
    validation_error = _validate(data, creating=False)
    if validation_error:
        return _error(validation_error)
    db = get_db()
    if db.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone() is None:
        return _error("Task not found", 404)
    assignments = list(data)
    values = [data[field].strip() if field == "title" else data[field] for field in assignments]
    assignments.append("updated_at")
    values.append(_now())
    values.append(task_id)
    db.execute(
        f"UPDATE tasks SET {', '.join(f'{field} = ?' for field in assignments)} WHERE id = ?",
        values,
    )
    db.commit()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return jsonify(_task_dict(task)), 200


@tasks.delete("/<int:task_id>")
def delete_task(task_id: int) -> tuple[str, int]:
    db = get_db()
    cursor = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    if cursor.rowcount == 0:
        return _error("Task not found", 404)
    return "", 204
