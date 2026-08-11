import os
import sqlite3
from datetime import datetime
from functools import wraps

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

DATABASE = os.environ.get("DATABASE", "todos.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  username TEXT NOT NULL UNIQUE,"
        "  password_hash TEXT NOT NULL"
        ")"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS tasks ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  title TEXT NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'pending',"
        "  created_at TEXT NOT NULL,"
        "  owner_id INTEGER,"
        "  FOREIGN KEY (owner_id) REFERENCES users (id)"
        ")"
    )
    try:
        db.execute(
            "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
        )
    except sqlite3.OperationalError:
        pass
    db.commit()


def create_user(username: str, password: str) -> dict | None:
    db = get_db()
    password_hash = generate_password_hash(password)
    try:
        cursor = db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        db.commit()
        return {"id": cursor.lastrowid, "username": username}
    except sqlite3.IntegrityError:
        return None


def get_user_by_username(username: str) -> dict | None:
    db = get_db()
    row = db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    return dict(row) if row else None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1]
        if not token:
            return jsonify({"error": "missing authorization token"}), 401
        try:
            payload = jwt.decode(token, app.secret_key, algorithms=["HS256"])
            g.user_id = payload["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid token"}), 401
        return f(*args, **kwargs)

    return decorated


def create_task(title: str, owner_id: int) -> dict:
    now = datetime.utcnow().isoformat()
    db = get_db()
    cursor = db.execute(
        "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
        (title, now, owner_id),
    )
    db.commit()
    return {
        "id": cursor.lastrowid,
        "title": title,
        "status": "pending",
        "created_at": now,
        "owner_id": owner_id,
    }


def get_tasks(owner_id: int):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
        (owner_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_task(task_id: int, owner_id: int) -> dict | None:
    db = get_db()
    row = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
        (task_id, owner_id),
    ).fetchone()
    return dict(row) if row else None


def update_task(
    task_id: int,
    owner_id: int,
    title: str | None = None,
    status: str | None = None,
) -> dict | None:
    task = get_task(task_id, owner_id)
    if task is None:
        return None
    db = get_db()
    updates = []
    params = []
    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if updates:
        params.append(task_id)
        db.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
        )
        db.commit()
    return get_task(task_id, owner_id)


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = create_user(username, password)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = get_user_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    token = jwt.encode({"user_id": user["id"]}, app.secret_key, algorithm="HS256")
    return jsonify({"token": token})


@app.route("/tasks", methods=["GET"])
@login_required
def list_tasks():
    return jsonify(get_tasks(g.user_id))


@app.route("/tasks", methods=["POST"])
@login_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title, g.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@login_required
def show_task(task_id: int):
    task = get_task(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@login_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    task = update_task(
        task_id,
        g.user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
