from datetime import datetime, timezone

from flask import g, jsonify, request

from .auth import auth_required
from .db import get_db


STATUSES = {"todo", "in_progress", "completed"}
PRIORITIES = {"low", "medium", "high", "urgent"}
TASK_SELECT = """
SELECT t.id, t.title, t.description, t.status, t.priority, t.due_date,
       t.category_id, c.name AS category_name, t.creator_id,
       creator.username AS creator_username, t.assignee_id,
       assignee.username AS assignee_username, t.created_at, t.updated_at
FROM tasks t
LEFT JOIN categories c ON c.id = t.category_id
JOIN users creator ON creator.id = t.creator_id
LEFT JOIN users assignee ON assignee.id = t.assignee_id
"""


def parse_due_date(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_references(db, data, errors):
    for field, table in (("category_id", "categories"), ("assignee_id", "users")):
        if field not in data or data[field] is None:
            continue
        if isinstance(data[field], bool) or not isinstance(data[field], int):
            errors[field] = f"{field} must be an integer or null"
        elif db.execute(f"SELECT 1 FROM {table} WHERE id = ?", (data[field],)).fetchone() is None:
            errors[field] = f"Referenced {field.removesuffix('_id')} does not exist"


def validate_task(data, partial=False):
    errors = {}
    if not partial or "title" in data:
        title = data.get("title")
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 200:
            errors["title"] = "Title must be between 1 and 200 characters"
    if "description" in data and (not isinstance(data["description"], str) or len(data["description"]) > 5000):
        errors["description"] = "Description must be a string up to 5000 characters"
    if "status" in data and data["status"] not in STATUSES:
        errors["status"] = f"Status must be one of: {', '.join(sorted(STATUSES))}"
    if "priority" in data and data["priority"] not in PRIORITIES:
        errors["priority"] = f"Priority must be one of: {', '.join(sorted(PRIORITIES))}"
    if "due_date" in data:
        try:
            parse_due_date(data["due_date"])
        except (ValueError, TypeError):
            errors["due_date"] = "Due date must be a valid ISO 8601 date-time"
    return errors


def fetch_task(db, task_id):
    return db.execute(TASK_SELECT + " WHERE t.id = ?", (task_id,)).fetchone()


def register_routes(app):
    @app.post("/api/tasks")
    @auth_required
    def create_task():
        data = request.get_json(silent=True) or {}
        errors = validate_task(data)
        db = get_db()
        validate_references(db, data, errors)
        if errors:
            return jsonify(error="Validation failed", details=errors), 400
        cursor = db.execute(
            "INSERT INTO tasks(title, description, status, priority, due_date, category_id, creator_id, assignee_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                data["title"].strip(), data.get("description", ""), data.get("status", "todo"),
                data.get("priority", "medium"), parse_due_date(data.get("due_date")),
                data.get("category_id"), g.user["id"], data.get("assignee_id"),
            ),
        )
        db.commit()
        return jsonify(task=dict(fetch_task(db, cursor.lastrowid))), 201

    @app.get("/api/tasks")
    @auth_required
    def list_tasks():
        try:
            page = int(request.args.get("page", 1))
            per_page = int(request.args.get("per_page", 20))
        except ValueError:
            return jsonify(error="page and per_page must be integers"), 400
        if page < 1 or per_page < 1 or per_page > 100:
            return jsonify(error="page must be positive and per_page must be between 1 and 100"), 400
        where, params = [], []
        for name, column, allowed in (
            ("status", "t.status", STATUSES), ("priority", "t.priority", PRIORITIES)
        ):
            value = request.args.get(name)
            if value:
                if value not in allowed:
                    return jsonify(error=f"Invalid {name}"), 400
                where.append(f"{column} = ?")
                params.append(value)
        category = request.args.get("category")
        if category:
            if category.isdigit():
                where.append("t.category_id = ?")
                params.append(int(category))
            else:
                where.append("c.name = ? COLLATE NOCASE")
                params.append(category)
        assignee_id = request.args.get("assignee_id")
        if assignee_id:
            if not assignee_id.isdigit():
                return jsonify(error="assignee_id must be an integer"), 400
            where.append("t.assignee_id = ?")
            params.append(int(assignee_id))
        search = request.args.get("q", "").strip()
        if search:
            where.append("(t.title LIKE ? OR t.description LIKE ?)")
            params.extend((f"%{search}%", f"%{search}%"))
        clause = " WHERE " + " AND ".join(where) if where else ""
        db = get_db()
        total = db.execute(
            "SELECT COUNT(*) FROM tasks t LEFT JOIN categories c ON c.id = t.category_id" + clause,
            params,
        ).fetchone()[0]
        rows = db.execute(
            TASK_SELECT + clause + " ORDER BY t.created_at DESC, t.id DESC LIMIT ? OFFSET ?",
            (*params, per_page, (page - 1) * per_page),
        ).fetchall()
        pages = (total + per_page - 1) // per_page
        return jsonify(
            tasks=[dict(row) for row in rows],
            pagination={"page": page, "per_page": per_page, "total": total, "pages": pages},
        )

    @app.get("/api/tasks/<int:task_id>")
    @auth_required
    def get_task(task_id):
        task = fetch_task(get_db(), task_id)
        if task is None:
            return jsonify(error="Task not found"), 404
        return jsonify(task=dict(task))

    @app.patch("/api/tasks/<int:task_id>")
    @auth_required
    def update_task(task_id):
        data = request.get_json(silent=True) or {}
        allowed = {"title", "description", "status", "priority", "due_date", "category_id", "assignee_id"}
        updates = {key: value for key, value in data.items() if key in allowed}
        if not updates:
            return jsonify(error="No updatable fields provided"), 400
        errors = validate_task(updates, partial=True)
        db = get_db()
        if fetch_task(db, task_id) is None:
            return jsonify(error="Task not found"), 404
        validate_references(db, updates, errors)
        if errors:
            return jsonify(error="Validation failed", details=errors), 400
        if "title" in updates:
            updates["title"] = updates["title"].strip()
        if "due_date" in updates:
            updates["due_date"] = parse_due_date(updates["due_date"])
        assignments = ", ".join(f"{key} = ?" for key in updates)
        db.execute(
            f"UPDATE tasks SET {assignments}, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
            (*updates.values(), task_id),
        )
        db.commit()
        return jsonify(task=dict(fetch_task(db, task_id)))

    @app.delete("/api/tasks/<int:task_id>")
    @auth_required
    def delete_task(task_id):
        db = get_db()
        cursor = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        db.commit()
        if cursor.rowcount == 0:
            return jsonify(error="Task not found"), 404
        return "", 204
