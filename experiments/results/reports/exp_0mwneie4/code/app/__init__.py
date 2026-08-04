import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash


class ApiError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(deque)

    def check(self, key, limit, window, now=None):
        now = now if now is not None else time.time()
        entries = self.requests[key]
        while entries and entries[0] <= now - window:
            entries.popleft()
        if len(entries) >= limit:
            return False, max(1, int(entries[0] + window - now) + 1)
        entries.append(now)
        return True, 0


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    owner_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER,
    action TEXT NOT NULL,
    resource TEXT NOT NULL,
    resource_id INTEGER,
    ip_address TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()


def json_body(required=(), optional=()):
    if not request.is_json:
        raise ApiError(415, "unsupported_media_type", "Content-Type must be application/json")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "invalid_json", "Request body must be a JSON object")
    allowed = set(required) | set(optional)
    errors = {}
    for field in required:
        if field not in data:
            errors[field] = "is required"
    for field in data.keys() - allowed:
        errors[field] = "is not allowed"
    if errors:
        raise ApiError(422, "validation_error", "Request validation failed", errors)
    return data


def validate_text(data, field, *, minimum=1, maximum=200, required=True):
    if field not in data and not required:
        return None
    value = data.get(field)
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ApiError(
            422,
            "validation_error",
            "Request validation failed",
            {field: f"must be a string between {minimum} and {maximum} characters"},
        )
    return value.strip()


def token_for(user_id):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=current_app.config["JWT_TTL_SECONDS"]),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def authenticated(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise ApiError(401, "authentication_required", "A bearer token is required")
        try:
            payload = jwt.decode(
                header[7:], current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            user_id = int(payload["sub"])
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            raise ApiError(401, "invalid_token", "The bearer token is invalid or expired")
        user = get_db().execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise ApiError(401, "invalid_token", "The token user no longer exists")
        g.user = user
        return view(*args, **kwargs)

    return wrapped


def audit(action, resource, resource_id=None, actor_id=None):
    get_db().execute(
        "INSERT INTO audit_logs (actor_id, action, resource, resource_id, ip_address, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (actor_id, action, resource, resource_id, request.remote_addr or "unknown", utcnow()),
    )


def item_json(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "owner_id": row["owner_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY="change-this-in-production",
        DATABASE="api.db",
        JWT_TTL_SECONDS=3600,
        RATE_LIMIT=100,
        RATE_LIMIT_WINDOW=60,
        MAX_PAGE_SIZE=100,
    )
    if config:
        app.config.update(config)
    app.extensions["rate_limiter"] = RateLimiter()

    @app.teardown_appcontext
    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.before_request
    def enforce_rate_limit():
        key = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
        allowed, retry_after = app.extensions["rate_limiter"].check(
            key, app.config["RATE_LIMIT"], app.config["RATE_LIMIT_WINDOW"]
        )
        if not allowed:
            error = ApiError(429, "rate_limit_exceeded", "Too many requests")
            error.retry_after = retry_after
            raise error

    @app.after_request
    def add_version_header(response):
        if request.path.startswith("/api/v1/"):
            response.headers["API-Version"] = "1"
        return response

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        body = {"error": {"code": error.code, "message": error.message}}
        if error.details:
            body["error"]["details"] = error.details
        response = jsonify(body)
        response.status_code = error.status
        if hasattr(error, "retry_after"):
            response.headers["Retry-After"] = str(error.retry_after)
        return response

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return jsonify(error={"code": error.name.lower().replace(" ", "_"), "message": error.description}), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled API error", exc_info=error)
        return jsonify(error={"code": "internal_error", "message": "An unexpected error occurred"}), 500

    @app.get("/api/v1/health")
    def health():
        return jsonify(status="ok", version="v1")

    @app.post("/api/v1/auth/register")
    def register():
        data = json_body(required=("username", "password"))
        username = validate_text(data, "username", minimum=3, maximum=50)
        password = validate_text(data, "password", minimum=8, maximum=128)
        db = get_db()
        try:
            cursor = db.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), utcnow()),
            )
        except sqlite3.IntegrityError:
            raise ApiError(409, "username_taken", "Username is already registered")
        user_id = cursor.lastrowid
        audit("register", "user", user_id, user_id)
        db.commit()
        return jsonify(id=user_id, username=username), 201

    @app.post("/api/v1/auth/login")
    def login():
        data = json_body(required=("username", "password"))
        username = validate_text(data, "username", minimum=1, maximum=50)
        password = validate_text(data, "password", minimum=1, maximum=128)
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            audit("login_failed", "user")
            db.commit()
            raise ApiError(401, "invalid_credentials", "Invalid username or password")
        audit("login", "user", user["id"], user["id"])
        db.commit()
        return jsonify(access_token=token_for(user["id"]), token_type="Bearer", expires_in=app.config["JWT_TTL_SECONDS"])

    @app.get("/api/v1/items")
    @authenticated
    def list_items():
        try:
            page = int(request.args.get("page", 1))
            per_page = int(request.args.get("per_page", 20))
        except ValueError:
            raise ApiError(422, "validation_error", "page and per_page must be integers")
        if page < 1 or not 1 <= per_page <= app.config["MAX_PAGE_SIZE"]:
            raise ApiError(422, "validation_error", "page must be positive and per_page must be within the allowed range")
        db = get_db()
        total = db.execute("SELECT COUNT(*) FROM items WHERE owner_id = ?", (g.user["id"],)).fetchone()[0]
        rows = db.execute(
            "SELECT * FROM items WHERE owner_id = ? ORDER BY id LIMIT ? OFFSET ?",
            (g.user["id"], per_page, (page - 1) * per_page),
        ).fetchall()
        pages = (total + per_page - 1) // per_page
        return jsonify(data=[item_json(row) for row in rows], pagination={"page": page, "per_page": per_page, "total": total, "pages": pages})

    @app.post("/api/v1/items")
    @authenticated
    def create_item():
        data = json_body(required=("name",), optional=("description",))
        name = validate_text(data, "name", maximum=100)
        description = validate_text(data, "description", minimum=0, maximum=500, required=False) or ""
        now = utcnow()
        db = get_db()
        cursor = db.execute(
            "INSERT INTO items (name, description, owner_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (name, description, g.user["id"], now, now),
        )
        audit("create", "item", cursor.lastrowid, g.user["id"])
        db.commit()
        row = db.execute("SELECT * FROM items WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(item_json(row)), 201

    @app.get("/api/v1/items/<int:item_id>")
    @authenticated
    def get_item(item_id):
        row = get_db().execute(
            "SELECT * FROM items WHERE id = ? AND owner_id = ?", (item_id, g.user["id"])
        ).fetchone()
        if row is None:
            raise ApiError(404, "not_found", "Item not found")
        return jsonify(item_json(row))

    @app.patch("/api/v1/items/<int:item_id>")
    @authenticated
    def update_item(item_id):
        data = json_body(optional=("name", "description"))
        if not data:
            raise ApiError(422, "validation_error", "At least one field is required")
        db = get_db()
        row = db.execute("SELECT * FROM items WHERE id = ? AND owner_id = ?", (item_id, g.user["id"])).fetchone()
        if row is None:
            raise ApiError(404, "not_found", "Item not found")
        name = validate_text(data, "name", maximum=100, required=False) or row["name"]
        description = validate_text(data, "description", minimum=0, maximum=500, required=False)
        description = row["description"] if description is None else description
        db.execute("UPDATE items SET name = ?, description = ?, updated_at = ? WHERE id = ?", (name, description, utcnow(), item_id))
        audit("update", "item", item_id, g.user["id"])
        db.commit()
        return jsonify(item_json(db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()))

    @app.delete("/api/v1/items/<int:item_id>")
    @authenticated
    def delete_item(item_id):
        db = get_db()
        cursor = db.execute("DELETE FROM items WHERE id = ? AND owner_id = ?", (item_id, g.user["id"]))
        if cursor.rowcount == 0:
            raise ApiError(404, "not_found", "Item not found")
        audit("delete", "item", item_id, g.user["id"])
        db.commit()
        return "", 204

    with app.app_context():
        init_db()

    return app
