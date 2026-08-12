"""
Minimal Flask Todo API with JWT authentication.

Models: User (id, username, password_hash) and Task (id, title, status,
created_at, owner_id). Tasks are scoped per user.

Data access is isolated behind a Repository layer; route handlers never
interact with SQLite directly.
"""

from abc import ABC, abstractmethod
from functools import wraps
from flask import Flask, request, jsonify
import bcrypt
import jwt
import sqlite3
import os
import time

from celery_config import send_notification_email

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
TOKEN_TTL = int(os.environ.get("TOKEN_TTL", 24 * 3600))


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL,"
            "  email TEXT"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at INTEGER NOT NULL,"
            "  owner_id INTEGER"
            ")"
        )
        # Migration: add owner_id to pre-existing task tables without dropping data.
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)")]
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        # Migration: add email to pre-existing user tables without dropping data.
        user_columns = [row["name"] for row in conn.execute("PRAGMA table_info(users)")]
        if "email" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.commit()


init_db()


# ── Repository layer ──────────────────────────────────────────

class BaseRepository(ABC):
    """Abstract base repository providing common CRUD operations."""

    @property
    @abstractmethod
    def table_name(self) -> str:
        """The name of the table this repository manages."""

    def _connect(self):
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn

    def get_by_id(self, obj_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (obj_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_all(self, **filters) -> list[dict]:
        with self._connect() as conn:
            if filters:
                where = " AND ".join(f"{key} = ?" for key in filters)
                rows = conn.execute(
                    f"SELECT * FROM {self.table_name} WHERE {where} ORDER BY id",
                    tuple(filters.values()),
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT * FROM {self.table_name} ORDER BY id"
                ).fetchall()
            return [dict(row) for row in rows]

    def create(self, **fields) -> dict:
        columns = list(fields)
        with self._connect() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table_name} ({', '.join(columns)}) "
                f"VALUES ({', '.join('?' for _ in columns)})",
                tuple(fields.values()),
            )
            conn.commit()
            obj = dict(fields)
            obj["id"] = cursor.lastrowid
            return obj

    def update(self, obj_id: int, **fields) -> dict | None:
        if self.get_by_id(obj_id) is None:
            return None
        if fields:
            assignments = ", ".join(f"{key} = ?" for key in fields)
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                    tuple(fields.values()) + (obj_id,),
                )
                conn.commit()
        return self.get_by_id(obj_id)

    def delete(self, obj_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (obj_id,)
            )
            conn.commit()
            return cursor.rowcount > 0


class UserRepository(BaseRepository):
    table_name = "users"

    def create_user(self, username: str, password: str, email: str | None = None) -> dict:
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        return self.create(username=username, password_hash=password_hash, email=email)

    def get_user(self, user_id: int) -> dict | None:
        return self.get_by_id(user_id)

    def get_user_by_username(self, username: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def create_task(self, title: str, owner_id: int) -> dict:
        now = int(time.time())
        return self.create(
            title=title, status="pending", created_at=now, owner_id=owner_id
        )

    def get_tasks(self, owner_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_task(self, task_id: int, owner_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def update_task(
        self,
        task_id: int,
        owner_id: int,
        title: str | None = None,
        status: str | None = None,
    ) -> dict | None:
        task = self.get_task(task_id, owner_id)
        if task is None:
            return None
        updates = {}
        if title is not None:
            updates["title"] = title
        if status is not None:
            updates["status"] = status
        if updates:
            self.update(task_id, **updates)
        return self.get_task(task_id, owner_id)


users_repo = UserRepository()
tasks_repo = TaskRepository()


# ── Auth helpers ──────────────────────────────────────────────

def verify_user(username: str, password: str) -> dict | None:
    user = users_repo.get_user_by_username(username)
    if user is None:
        return None
    if not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        return None
    return user


def make_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_TTL,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def get_auth_user() -> dict | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[len("Bearer "):].strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return users_repo.get_user(payload.get("user_id"))


def auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_auth_user()
        if user is None:
            return jsonify({"error": "unauthorized"}), 401
        kwargs["user_id"] = user["id"]
        return f(*args, **kwargs)

    return wrapper


# ── Routes: auth ──────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = (data.get("email") or "").strip() or None
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    if users_repo.get_user_by_username(username) is not None:
        return jsonify({"error": "username already exists"}), 409
    user = users_repo.create_user(username, password, email)
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    user = verify_user(username, password)
    if user is None:
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": make_token(user["id"])}), 200


# ── Routes: tasks (all protected) ─────────────────────────────

@app.route("/tasks", methods=["GET"])
@auth_required
def list_tasks(user_id: int):
    return jsonify(tasks_repo.get_tasks(user_id))


@app.route("/tasks", methods=["POST"])
@auth_required
def add_task(user_id: int):
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = tasks_repo.create_task(title, user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@auth_required
def show_task(task_id: int, user_id: int):
    task = tasks_repo.get_task(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@auth_required
def edit_task(task_id: int, user_id: int):
    data = request.get_json(silent=True) or {}
    previous = tasks_repo.get_task(task_id, user_id)
    task = tasks_repo.update_task(
        task_id,
        user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if (
        previous is not None
        and previous["status"] != "completed"
        and task["status"] == "completed"
    ):
        owner = users_repo.get_user(user_id) or {}
        recipient = owner.get("email") or owner.get("username")
        send_notification_email.delay(recipient, task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
