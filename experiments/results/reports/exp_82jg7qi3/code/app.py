import json
import os
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

import jwt
from flask import Flask, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash


API_PREFIX = "/api/v1"


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(Path(app.instance_path) / "api.sqlite3"),
        JWT_SECRET=os.environ.get("JWT_SECRET", "change-this-secret-in-production"),
        JWT_TTL_SECONDS=3600,
        RATE_LIMIT=60,
        RATE_WINDOW_SECONDS=60,
        MAX_CONTENT_LENGTH=1_000_000,
    )
    if config:
        app.config.update(config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    rate_buckets = defaultdict(deque)

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    def init_db():
        db = get_db()
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id INTEGER,
                outcome TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            """
        )
        db.commit()

    def now_iso():
        return datetime.now(timezone.utc).isoformat()

    def audit(action, resource_type, resource_id=None, outcome="success", details=None, user_id=None):
        db = get_db()
        db.execute(
            """INSERT INTO audit_logs
               (user_id, action, resource_type, resource_id, outcome, ip_address, details, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id if user_id is not None else getattr(g, "user_id", None),
                action,
                resource_type,
                resource_id,
                outcome,
                request.remote_addr or "unknown",
                json.dumps(details or {}, separators=(",", ":")),
                now_iso(),
            ),
        )
        db.commit()

    def error(message, status, code):
        return jsonify({"error": {"code": code, "message": message}}), status

    def json_body(required, optional=()):
        if not request.is_json:
            return None, error("Content-Type must be application/json", 415, "unsupported_media_type")
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return None, error("Request body must be a JSON object", 400, "invalid_json")
        allowed = set(required) | set(optional)
        unknown = sorted(set(data) - allowed)
        missing = sorted(field for field in required if field not in data)
        if missing or unknown:
            parts = []
            if missing:
                parts.append(f"missing fields: {', '.join(missing)}")
            if unknown:
                parts.append(f"unknown fields: {', '.join(unknown)}")
            return None, error("; ".join(parts), 422, "validation_error")
        return data, None

    def pagination():
        try:
            page = int(request.args.get("page", 1))
            per_page = int(request.args.get("per_page", 20))
        except ValueError:
            return None, error("page and per_page must be integers", 422, "validation_error")
        if page < 1 or not 1 <= per_page <= 100:
            return None, error("page must be >= 1 and per_page must be between 1 and 100", 422, "validation_error")
        return (page, per_page), None

    def require_auth(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            value = request.headers.get("Authorization", "")
            if not value.startswith("Bearer "):
                return error("A Bearer token is required", 401, "authentication_required")
            try:
                payload = jwt.decode(
                    value[7:],
                    current_app.config["JWT_SECRET"],
                    algorithms=["HS256"],
                    options={"require": ["exp", "iat", "sub"]},
                )
                g.user_id = int(payload["sub"])
            except (jwt.PyJWTError, TypeError, ValueError):
                return error("Token is invalid or expired", 401, "invalid_token")
            user = get_db().execute("SELECT id FROM users WHERE id = ?", (g.user_id,)).fetchone()
            if user is None:
                return error("Token subject no longer exists", 401, "invalid_token")
            return view(*args, **kwargs)

        return wrapped

    @app.before_request
    def enforce_rate_limit():
        if not request.path.startswith(API_PREFIX):
            return None
        limit = current_app.config["RATE_LIMIT"]
        window = current_app.config["RATE_WINDOW_SECONDS"]
        key = request.remote_addr or "unknown"
        bucket = rate_buckets[key]
        now = time.monotonic()
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(1, int(window - (now - bucket[0])) + 1)
            response, status = error("Rate limit exceeded", 429, "rate_limit_exceeded")
            response.headers["Retry-After"] = str(retry_after)
            response.headers["X-RateLimit-Limit"] = str(limit)
            return response, status
        bucket.append(now)
        g.rate_limit_remaining = limit - len(bucket)
        return None

    @app.after_request
    def add_rate_headers(response):
        if request.path.startswith(API_PREFIX):
            response.headers.setdefault("X-RateLimit-Limit", str(current_app.config["RATE_LIMIT"]))
            if hasattr(g, "rate_limit_remaining"):
                response.headers.setdefault("X-RateLimit-Remaining", str(g.rate_limit_remaining))
        return response

    @app.teardown_appcontext
    def close_db(_exception):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        return error(exc.description, exc.code, exc.name.lower().replace(" ", "_"))

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc):
        current_app.logger.exception("Unhandled API error", exc_info=exc)
        return error("An unexpected error occurred", 500, "internal_server_error")

    @app.get(f"{API_PREFIX}/health")
    def health():
        return jsonify({"status": "ok", "version": "v1"})

    @app.post(f"{API_PREFIX}/auth/register")
    def register():
        data, problem = json_body(("username", "password"))
        if problem:
            return problem
        username = data["username"]
        password = data["password"]
        if not isinstance(username, str) or not 3 <= len(username.strip()) <= 50:
            return error("username must contain 3 to 50 characters", 422, "validation_error")
        if not isinstance(password, str) or len(password) < 8:
            return error("password must contain at least 8 characters", 422, "validation_error")
        db = get_db()
        try:
            cursor = db.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username.strip(), generate_password_hash(password), now_iso()),
            )
            db.commit()
        except sqlite3.IntegrityError:
            audit("register", "user", outcome="failure", details={"reason": "duplicate_username"})
            return error("username is already registered", 409, "conflict")
        audit("register", "user", cursor.lastrowid, user_id=cursor.lastrowid)
        return jsonify({"id": cursor.lastrowid, "username": username.strip()}), 201

    @app.post(f"{API_PREFIX}/auth/login")
    def login():
        data, problem = json_body(("username", "password"))
        if problem:
            return problem
        if not isinstance(data["username"], str) or not isinstance(data["password"], str):
            return error("username and password must be strings", 422, "validation_error")
        user = get_db().execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?", (data["username"].strip(),)
        ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], data["password"]):
            audit("login", "session", outcome="failure", details={"reason": "invalid_credentials"})
            return error("Invalid username or password", 401, "invalid_credentials")
        issued = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": str(user["id"]),
                "iat": issued,
                "exp": issued + timedelta(seconds=current_app.config["JWT_TTL_SECONDS"]),
            },
            current_app.config["JWT_SECRET"],
            algorithm="HS256",
        )
        audit("login", "session", user_id=user["id"])
        return jsonify({"access_token": token, "token_type": "Bearer", "expires_in": current_app.config["JWT_TTL_SECONDS"]})

    def serialize_item(row):
        return {key: row[key] for key in ("id", "name", "description", "created_at", "updated_at")}

    @app.get(f"{API_PREFIX}/items")
    @require_auth
    def list_items():
        values, problem = pagination()
        if problem:
            return problem
        page, per_page = values
        db = get_db()
        total = db.execute("SELECT COUNT(*) FROM items WHERE user_id = ?", (g.user_id,)).fetchone()[0]
        rows = db.execute(
            "SELECT * FROM items WHERE user_id = ? ORDER BY id LIMIT ? OFFSET ?",
            (g.user_id, per_page, (page - 1) * per_page),
        ).fetchall()
        pages = (total + per_page - 1) // per_page
        return jsonify({
            "data": [serialize_item(row) for row in rows],
            "pagination": {"page": page, "per_page": per_page, "total": total, "pages": pages},
        })

    @app.post(f"{API_PREFIX}/items")
    @require_auth
    def create_item():
        data, problem = json_body(("name",), ("description",))
        if problem:
            return problem
        name = data["name"]
        description = data.get("description", "")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
            return error("name must contain 1 to 100 characters", 422, "validation_error")
        if not isinstance(description, str) or len(description) > 1000:
            return error("description must be a string of at most 1000 characters", 422, "validation_error")
        timestamp = now_iso()
        db = get_db()
        cursor = db.execute(
            "INSERT INTO items (user_id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (g.user_id, name.strip(), description, timestamp, timestamp),
        )
        db.commit()
        audit("create", "item", cursor.lastrowid)
        row = db.execute("SELECT * FROM items WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(serialize_item(row)), 201

    def owned_item(item_id):
        return get_db().execute(
            "SELECT * FROM items WHERE id = ? AND user_id = ?", (item_id, g.user_id)
        ).fetchone()

    @app.get(f"{API_PREFIX}/items/<int:item_id>")
    @require_auth
    def get_item(item_id):
        row = owned_item(item_id)
        if row is None:
            return error("Item not found", 404, "not_found")
        return jsonify(serialize_item(row))

    @app.patch(f"{API_PREFIX}/items/<int:item_id>")
    @require_auth
    def update_item(item_id):
        row = owned_item(item_id)
        if row is None:
            return error("Item not found", 404, "not_found")
        data, problem = json_body((), ("name", "description"))
        if problem:
            return problem
        if not data:
            return error("At least one field is required", 422, "validation_error")
        name = data.get("name", row["name"])
        description = data.get("description", row["description"])
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
            return error("name must contain 1 to 100 characters", 422, "validation_error")
        if not isinstance(description, str) or len(description) > 1000:
            return error("description must be a string of at most 1000 characters", 422, "validation_error")
        db = get_db()
        db.execute(
            "UPDATE items SET name = ?, description = ?, updated_at = ? WHERE id = ?",
            (name.strip(), description, now_iso(), item_id),
        )
        db.commit()
        audit("update", "item", item_id)
        return jsonify(serialize_item(owned_item(item_id)))

    @app.delete(f"{API_PREFIX}/items/<int:item_id>")
    @require_auth
    def delete_item(item_id):
        if owned_item(item_id) is None:
            return error("Item not found", 404, "not_found")
        db = get_db()
        db.execute("DELETE FROM items WHERE id = ?", (item_id,))
        db.commit()
        audit("delete", "item", item_id)
        return "", 204

    @app.get(f"{API_PREFIX}/audit-logs")
    @require_auth
    def list_audit_logs():
        values, problem = pagination()
        if problem:
            return problem
        page, per_page = values
        db = get_db()
        total = db.execute("SELECT COUNT(*) FROM audit_logs WHERE user_id = ?", (g.user_id,)).fetchone()[0]
        rows = db.execute(
            """SELECT id, action, resource_type, resource_id, outcome, ip_address, details, created_at
               FROM audit_logs WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?""",
            (g.user_id, per_page, (page - 1) * per_page),
        ).fetchall()
        data = []
        for row in rows:
            entry = dict(row)
            entry["details"] = json.loads(entry["details"])
            data.append(entry)
        return jsonify({
            "data": data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page,
            },
        })

    with app.app_context():
        init_db()

    return app


if __name__ == "__main__":
    create_app().run()
