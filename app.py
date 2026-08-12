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
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
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

RATE_LIMIT = os.environ.get("RATE_LIMIT", "100 per minute")
RATE_LIMIT_STORAGE = os.environ.get(
    "RATE_LIMIT_STORAGE", "redis://localhost:6379/0"
)
RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100


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

    def get_tasks_page(
        self,
        owner_id: int,
        cursor: int | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
    ) -> tuple[list[dict], int, int | None]:
        """Return (tasks, total, next_cursor) for cursor-based pagination.

        Tasks are ordered by id descending; ``cursor`` is the id of the last
        item from the previous page, so we fetch items with a strictly
        smaller id. ``next_cursor`` is the id of the last item returned on
        this page, or None when there are no more items.
        """
        query = "SELECT * FROM tasks WHERE owner_id = ?"
        params: list = [owner_id]
        if cursor is not None:
            query += " AND id < ?"
            params.append(cursor)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit + 1)

        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS count FROM tasks WHERE owner_id = ?",
                (owner_id,),
            ).fetchone()["count"]
            rows = [dict(row) for row in conn.execute(query, tuple(params)).fetchall()]

        next_cursor = None
        if len(rows) > limit:
            next_cursor = rows[limit - 1]["id"]
            rows = rows[:limit]
        return rows, total, next_cursor

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


# ── Rate limiting ─────────────────────────────────────────────

def rate_limit_key(*args, **kwargs) -> str:
    """Key each request by authenticated user id, falling back to client IP.

    This keeps the 100-requests-per-minute bucket scoped per user while still
    applying a limit to unauthenticated endpoints such as register/login.
    """
    user = get_auth_user()
    if user is not None:
        return f"user:{user['id']}"
    return f"ip:{get_remote_address()}"


limiter = Limiter(
    rate_limit_key,
    app=app,
    application_limits=[RATE_LIMIT],
    enabled=RATE_LIMIT_ENABLED,
    storage_uri=RATE_LIMIT_STORAGE,
    headers_enabled=True,
)


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
    limit = request.args.get("limit", type=int) or DEFAULT_PAGE_LIMIT
    if limit < 1:
        limit = DEFAULT_PAGE_LIMIT
    limit = min(limit, MAX_PAGE_LIMIT)

    cursor = request.args.get("cursor")
    if cursor is not None and cursor != "":
        try:
            cursor = int(cursor)
        except (TypeError, ValueError):
            return jsonify({"error": "cursor must be an integer"}), 400
    else:
        cursor = None

    data, total, next_cursor = tasks_repo.get_tasks_page(
        user_id, cursor=cursor, limit=limit
    )
    return jsonify(
        {
            "data": data,
            "next_cursor": str(next_cursor) if next_cursor is not None else None,
            "total": total,
        }
    )


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
