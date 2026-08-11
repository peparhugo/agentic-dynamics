import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key"


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db_path = current_app.config.get("DATABASE", "tasks.db")
        db = g._database = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
    return db


def init_db():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            owner_id INTEGER REFERENCES user(id)
        )
        """
    )
    try:
        db.execute(
            "ALTER TABLE task ADD COLUMN owner_id INTEGER REFERENCES user(id)"
        )
    except sqlite3.OperationalError:
        pass
    db.commit()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def task_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid token"}), 401
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Missing or invalid token"}), 401
        db = get_db()
        user = db.execute(
            "SELECT id FROM user WHERE id = ?", (payload["user_id"],)
        ).fetchone()
        if not user:
            return jsonify({"error": "Missing or invalid token"}), 401
        g.current_user_id = user["id"]
        return f(*args, **kwargs)

    return decorated


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "Username and password are required"}), 400

    username = data["username"]
    password = data["password"]
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "Username and password are required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "Username and password are required"}), 400

    db = get_db()
    existing = db.execute(
        "SELECT id FROM user WHERE username = ?", (username.strip(),)
    ).fetchone()
    if existing:
        return jsonify({"error": "Username already exists"}), 409

    password_hash = generate_password_hash(password)
    cursor = db.execute(
        "INSERT INTO user (username, password_hash) VALUES (?, ?)",
        (username.strip(), password_hash),
    )
    db.commit()
    return jsonify({"id": cursor.lastrowid, "username": username.strip()}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "Username and password are required"}), 400

    username = data["username"]
    password = data["password"]

    db = get_db()
    user = db.execute(
        "SELECT * FROM user WHERE username = ?", (username,)
    ).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid username or password"}), 401

    payload = {
        "user_id": user["id"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    token = jwt.encode(
        payload, current_app.config["SECRET_KEY"], algorithm="HS256"
    )
    return jsonify({"token": token}), 200


@app.route("/tasks", methods=["POST"])
@require_auth
def create_task():
    data = request.get_json(silent=True)
    if not data or "title" not in data:
        return jsonify({"error": "Title is required"}), 400

    title = data["title"]
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "Title is required"}), 400

    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    cursor = db.execute(
        "INSERT INTO task (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
        (title.strip(), now, g.current_user_id),
    )
    db.commit()

    task_id = cursor.lastrowid
    row = db.execute(
        "SELECT * FROM task WHERE id = ? AND owner_id = ?",
        (task_id, g.current_user_id),
    ).fetchone()
    return jsonify(task_to_dict(row)), 201


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM task WHERE owner_id = ? ORDER BY created_at DESC",
        (g.current_user_id,),
    ).fetchall()
    return jsonify([task_to_dict(r) for r in rows]), 200


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(task_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM task WHERE id = ? AND owner_id = ?",
        (task_id, g.current_user_id),
    ).fetchone()
    if row is None:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task_to_dict(row)), 200


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(task_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM task WHERE id = ? AND owner_id = ?",
        (task_id, g.current_user_id),
    ).fetchone()
    if row is None:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify(task_to_dict(row)), 200

    title = data.get("title", row["title"])
    status = data.get("status", row["status"])

    if isinstance(title, str) and not title.strip():
        return jsonify({"error": "Title is required"}), 400

    db.execute(
        "UPDATE task SET title = ?, status = ? WHERE id = ? AND owner_id = ?",
        (
            title.strip() if isinstance(title, str) else title,
            status,
            task_id,
            g.current_user_id,
        ),
    )
    db.commit()

    row = db.execute(
        "SELECT * FROM task WHERE id = ? AND owner_id = ?",
        (task_id, g.current_user_id),
    ).fetchone()
    return jsonify(task_to_dict(row)), 200


with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
