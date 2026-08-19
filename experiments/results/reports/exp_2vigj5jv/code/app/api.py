from datetime import date

from flask import Blueprint, current_app, g, jsonify, request

from .auth import make_token, password_hash, password_matches, token_required

api = Blueprint("api", __name__)
VALID_STATUSES = {"todo", "in_progress", "completed", "cancelled"}
VALID_PRIORITIES = {"low", "medium", "high", "urgent"}


def body():
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else {}


def user_json(user):
    return {"id": user["id"], "username": user["username"], "email": user["email"]}


def task_json(row):
    result = dict(row)
    result["assignee"] = None
    if result.get("assignee_id") is not None:
        result["assignee"] = {"id": result.pop("assignee_id"), "username": result.pop("assignee_username")}
    else:
        result.pop("assignee_id", None)
        result.pop("assignee_username", None)
    return result


@api.post("/auth/register")
def register():
    data = body()
    username, email, password = data.get("username"), data.get("email"), data.get("password")
    if not all(isinstance(x, str) and x.strip() for x in (username, email, password)) or len(password) < 8:
        return jsonify(error="username, email, and a password of at least 8 characters are required"), 400
    db = current_app.get_db()
    try:
        cursor = db.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", (username.strip(), email.strip().lower(), password_hash(password)))
        db.commit()
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            return jsonify(error="username or email already exists"), 409
        raise
    user = db.execute("SELECT id, username, email FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(user=user_json(user), token=make_token(user["id"])), 201


@api.post("/auth/login")
def login():
    data = body()
    identity, password = data.get("username") or data.get("email"), data.get("password")
    user = current_app.get_db().execute("SELECT * FROM users WHERE username = ? OR email = ?", (identity, identity)).fetchone() if isinstance(identity, str) else None
    if user is None or not isinstance(password, str) or not password_matches(password, user["password_hash"]):
        return jsonify(error="invalid credentials"), 401
    return jsonify(user=user_json(user), token=make_token(user["id"])), 200


@api.get("/auth/me")
@token_required
def me():
    return jsonify(user=user_json(g.current_user))


def access_clause():
    return "(t.owner_id = ? OR t.assignee_id = ?)", (g.current_user["id"], g.current_user["id"])


@api.route("/tasks", methods=["GET", "POST"])
@token_required
def tasks():
    db = current_app.get_db()
    if request.method == "GET":
        conditions, params = [access_clause()[0]], list(access_clause()[1])
        for key, column in (("status", "t.status"), ("category", "t.category"), ("priority", "t.priority")):
            if request.args.get(key):
                conditions.append(f"{column} = ?")
                params.append(request.args[key])
        if request.args.get("search"):
            conditions.append("(LOWER(t.title) LIKE ? OR LOWER(COALESCE(t.description, '')) LIKE ?)")
            term = f"%{request.args['search'].lower()}%"
            params.extend([term, term])
        try:
            page, per_page = max(int(request.args.get("page", 1)), 1), min(max(int(request.args.get("per_page", 20)), 1), 100)
        except ValueError:
            return jsonify(error="page and per_page must be integers"), 400
        where = " AND ".join(conditions)
        total = db.execute(f"SELECT COUNT(*) FROM tasks t WHERE {where}", params).fetchone()[0]
        rows = db.execute(f"SELECT t.*, u.username AS assignee_username FROM tasks t LEFT JOIN users u ON u.id=t.assignee_id WHERE {where} ORDER BY t.created_at DESC LIMIT ? OFFSET ?", params + [per_page, (page - 1) * per_page]).fetchall()
        return jsonify(tasks=[task_json(row) for row in rows], pagination={"page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page})

    data = body()
    error = validate_task(data, required=True)
    if error:
        return jsonify(error=error), 400
    assignee_id, error = assignee(data.get("assignee_id"), db)
    if error:
        return jsonify(error=error), 400
    cursor = db.execute("INSERT INTO tasks (title, description, status, category, priority, due_date, owner_id, assignee_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (data["title"].strip(), data.get("description"), data.get("status", "todo"), data.get("category"), data.get("priority", "medium"), data.get("due_date"), g.current_user["id"], assignee_id))
    db.commit()
    row = db.execute("SELECT t.*, u.username AS assignee_username FROM tasks t LEFT JOIN users u ON u.id=t.assignee_id WHERE t.id=?", (cursor.lastrowid,)).fetchone()
    return jsonify(task=task_json(row)), 201


@api.route("/tasks/<int:task_id>", methods=["GET", "PUT", "PATCH", "DELETE"])
@token_required
def task(task_id):
    db = current_app.get_db()
    row = db.execute("SELECT t.*, u.username AS assignee_username FROM tasks t LEFT JOIN users u ON u.id=t.assignee_id WHERE t.id=?", (task_id,)).fetchone()
    if row is None:
        return jsonify(error="task not found"), 404
    if row["owner_id"] != g.current_user["id"] and row["assignee_id"] != g.current_user["id"]:
        return jsonify(error="forbidden"), 403
    if request.method == "GET":
        return jsonify(task=task_json(row))
    if request.method == "DELETE":
        if row["owner_id"] != g.current_user["id"]:
            return jsonify(error="only the owner can delete a task"), 403
        db.execute("DELETE FROM tasks WHERE id=?", (task_id,)); db.commit()
        return "", 204
    data = body()
    error = validate_task(data, required=False)
    if error:
        return jsonify(error=error), 400
    assignee_id, error = assignee(data.get("assignee_id", row["assignee_id"]), db)
    if error:
        return jsonify(error=error), 400
    fields = {key: data[key] for key in ("title", "description", "status", "category", "priority", "due_date") if key in data}
    if "title" in fields: fields["title"] = fields["title"].strip()
    fields["assignee_id"] = assignee_id
    if row["owner_id"] != g.current_user["id"] and any(key in data for key in ("title", "assignee_id", "owner_id")):
        return jsonify(error="only the owner can change task ownership or assignment"), 403
    if fields:
        db.execute(f"UPDATE tasks SET {', '.join(f'{key}=?' for key in fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=?", list(fields.values()) + [task_id]); db.commit()
    updated = db.execute("SELECT t.*, u.username AS assignee_username FROM tasks t LEFT JOIN users u ON u.id=t.assignee_id WHERE t.id=?", (task_id,)).fetchone()
    return jsonify(task=task_json(updated))


def validate_task(data, required):
    if required and (not isinstance(data.get("title"), str) or not data["title"].strip()): return "title is required"
    if "status" in data and data["status"] not in VALID_STATUSES: return "invalid status"
    if "priority" in data and data["priority"] not in VALID_PRIORITIES: return "invalid priority"
    if "due_date" in data and data["due_date"] is not None:
        try: date.fromisoformat(data["due_date"])
        except (TypeError, ValueError): return "due_date must be YYYY-MM-DD"
    return None


def assignee(value, db):
    if value is None: return None, None
    try: value = int(value)
    except (TypeError, ValueError): return None, "assignee_id must be an integer"
    if db.execute("SELECT id FROM users WHERE id=?", (value,)).fetchone() is None: return None, "assignee does not exist"
    return value, None
