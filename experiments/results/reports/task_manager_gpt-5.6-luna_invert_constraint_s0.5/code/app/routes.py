import re
from datetime import date
from flask import Blueprint, g, jsonify, request
from werkzeug.exceptions import BadRequest
from .auth import check_password_hash, create_token, generate_password_hash, login_required
from .db import get_db

api = Blueprint("api", __name__)
STATUSES = {"pending", "in_progress", "completed", "cancelled"}
PRIORITIES = {"low", "medium", "high", "urgent"}


def error(message, status=400):
    return jsonify(error=message), status


def body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def task_json(row):
    result = dict(row)
    result["category"] = result.pop("category_name", None)
    return result


@api.post("/auth/register")
def register():
    data = body()
    if not data or not all(isinstance(data.get(k), str) and data[k].strip() for k in ("username", "email", "password")):
        return error("username, email, and password are required")
    if len(data["password"]) < 8 or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", data["email"]):
        return error("password must be at least 8 characters and email must be valid")
    db = get_db()
    try:
        cursor = db.execute("INSERT INTO users(username,email,password_hash) VALUES (?,?,?)", (data["username"].strip(), data["email"].strip(), generate_password_hash(data["password"])))
        db.commit()
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            return error("username or email already exists", 409)
        raise
    user_id = cursor.lastrowid
    return jsonify(user={"id": user_id, "username": data["username"].strip(), "email": data["email"].strip()}, token=create_token(user_id)), 201


@api.post("/auth/login")
def login():
    data = body()
    if not data or not data.get("username") or not data.get("password"):
        return error("username and password are required")
    user = get_db().execute("SELECT * FROM users WHERE username = ? OR email = ?", (data["username"], data["username"])).fetchone()
    if not user or not check_password_hash(user["password_hash"], data["password"]):
        return error("invalid credentials", 401)
    return jsonify(user={"id": user["id"], "username": user["username"], "email": user["email"]}, token=create_token(user["id"]))


@api.get("/auth/me")
@login_required
def me():
    return jsonify(user=dict(g.user))


@api.get("/categories")
@login_required
def categories():
    rows = get_db().execute("SELECT id, name FROM categories WHERE user_id = ? ORDER BY name", (g.user["id"],)).fetchall()
    return jsonify(categories=[dict(row) for row in rows])


@api.post("/categories")
@login_required
def create_category():
    data = body()
    if not data or not isinstance(data.get("name"), str) or not data["name"].strip():
        return error("name is required")
    try:
        cur = get_db().execute("INSERT INTO categories(user_id,name) VALUES (?,?)", (g.user["id"], data["name"].strip()))
        get_db().commit()
    except Exception as exc:
        if "UNIQUE" in str(exc).upper(): return error("category already exists", 409)
        raise
    return jsonify(category={"id": cur.lastrowid, "name": data["name"].strip()}), 201


def _task_select(where="", params=(), limit=None, offset=None):
    query = "SELECT t.*, c.name AS category_name, u.username AS assignee_username FROM tasks t LEFT JOIN categories c ON c.id=t.category_id LEFT JOIN users u ON u.id=t.assigned_to " + where + " ORDER BY t.created_at DESC, t.id DESC"
    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        params = list(params) + [limit, offset]
    return get_db().execute(query, params).fetchall()


@api.get("/tasks")
@login_required
def list_tasks():
    clauses = ["(t.user_id = ? OR t.assigned_to = ?)"]
    params = [g.user["id"], g.user["id"]]
    for field in ("status", "priority"):
        if request.args.get(field):
            if request.args[field] not in (STATUSES if field == "status" else PRIORITIES): return error(f"invalid {field}")
            clauses.append(f"t.{field} = ?"); params.append(request.args[field])
    if request.args.get("category"):
        clauses.append("(c.name = ? OR CAST(t.category_id AS TEXT) = ?)"); params.extend([request.args["category"], request.args["category"]])
    if request.args.get("q"):
        clauses.append("(t.title LIKE ? OR t.description LIKE ?)"); params.extend([f"%{request.args['q']}%"] * 2)
    try:
        page, per_page = max(1, int(request.args.get("page", 1))), min(100, max(1, int(request.args.get("per_page", 20))))
    except ValueError: return error("page and per_page must be integers")
    where = " WHERE " + " AND ".join(clauses)
    total = get_db().execute("SELECT COUNT(*) FROM tasks t LEFT JOIN categories c ON c.id=t.category_id" + where, params).fetchone()[0]
    rows = _task_select(where, params, per_page, (page - 1) * per_page)
    return jsonify(tasks=[task_json(r) for r in rows], pagination={"page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page})


@api.post("/tasks")
@login_required
def create_task():
    data = body()
    if not data or not isinstance(data.get("title"), str) or not data["title"].strip(): return error("title is required")
    status, priority = data.get("status", "pending"), data.get("priority", "medium")
    if status not in STATUSES: return error("invalid status")
    if priority not in PRIORITIES: return error("invalid priority")
    due = data.get("due_date")
    if due:
        try: date.fromisoformat(due)
        except (TypeError, ValueError): return error("due_date must be YYYY-MM-DD")
    db = get_db(); category_id = data.get("category_id")
    if category_id is not None and not db.execute("SELECT 1 FROM categories WHERE id=? AND user_id=?", (category_id, g.user["id"])).fetchone(): return error("category not found", 404)
    assignee = data.get("assigned_to")
    if assignee is not None and not db.execute("SELECT 1 FROM users WHERE id=?", (assignee,)).fetchone(): return error("assigned user not found", 404)
    cur = db.execute("INSERT INTO tasks(user_id,assigned_to,category_id,title,description,status,priority,due_date) VALUES (?,?,?,?,?,?,?,?)", (g.user["id"], assignee, category_id, data["title"].strip(), data.get("description", ""), status, priority, due)); db.commit()
    row = _task_select("WHERE t.id = ?", (cur.lastrowid,))[0]
    return jsonify(task=task_json(row)), 201


@api.get("/tasks/<int:task_id>")
@login_required
def get_task(task_id):
    row = _task_select("WHERE t.id=? AND (t.user_id=? OR t.assigned_to=?)", (task_id, g.user["id"], g.user["id"]))
    return jsonify(task=task_json(row[0])) if row else error("task not found", 404)


@api.route("/tasks/<int:task_id>", methods=["PUT", "PATCH"])
@login_required
def update_task(task_id):
    db = get_db(); existing = db.execute("SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, g.user["id"])).fetchone()
    if not existing: return error("task not found", 404)
    data = body()
    if not data: return error("JSON object is required")
    fields, values = [], []
    allowed = {"title", "description", "status", "priority", "due_date", "assigned_to", "category_id"}
    for key, value in data.items():
        if key not in allowed: continue
        if key == "status" and value not in STATUSES: return error("invalid status")
        if key == "priority" and value not in PRIORITIES: return error("invalid priority")
        if key == "due_date" and value:
            try: date.fromisoformat(value)
            except (TypeError, ValueError): return error("due_date must be YYYY-MM-DD")
        if key == "assigned_to" and value is not None and not db.execute("SELECT 1 FROM users WHERE id=?", (value,)).fetchone(): return error("assigned user not found", 404)
        if key == "category_id" and value is not None and not db.execute("SELECT 1 FROM categories WHERE id=? AND user_id=?", (value, g.user["id"])).fetchone(): return error("category not found", 404)
        fields.append(f"{key}=?"); values.append(value.strip() if key == "title" and isinstance(value, str) else value)
    if "title" in data and not isinstance(data["title"], str) or "title" in data and not data["title"].strip(): return error("title cannot be empty")
    if fields: db.execute("UPDATE tasks SET " + ",".join(fields) + ",updated_at=CURRENT_TIMESTAMP WHERE id=?", values + [task_id]); db.commit()
    row = _task_select("WHERE t.id=?", (task_id,))[0]
    return jsonify(task=task_json(row))


@api.delete("/tasks/<int:task_id>")
@login_required
def delete_task(task_id):
    db = get_db(); cur = db.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, g.user["id"])); db.commit()
    return ("", 204) if cur.rowcount else error("task not found", 404)
