import os
import re
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from functools import wraps

import jwt
from flask import Flask, current_app, g, jsonify, request
from werkzeug.exceptions import BadRequest, HTTPException
from werkzeug.security import check_password_hash, generate_password_hash


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class APIError(Exception):
    def __init__(self, status, code, message, details=None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("DATABASE", "api.db"),
        JWT_SECRET=os.environ.get("JWT_SECRET", "development-only-change-me"),
        JWT_TTL_SECONDS=3600,
        RATE_LIMIT=100,
        RATE_WINDOW_SECONDS=60,
        MAX_PAGE_SIZE=100,
    )
    if config:
        app.config.update(config)

    rate_buckets = {}

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    def init_db():
        db = sqlite3.connect(app.config["DATABASE"])
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id INTEGER,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                status INTEGER NOT NULL,
                ip_address TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        db.close()

    app.get_db = get_db
    app.init_db = init_db
    init_db()

    def json_body():
        if not request.is_json:
            raise APIError(415, "unsupported_media_type", "Content-Type must be application/json")
        try:
            value = request.get_json()
        except BadRequest as exc:
            raise APIError(400, "invalid_json", "Request body contains invalid JSON") from exc
        if not isinstance(value, dict):
            raise APIError(400, "validation_error", "Request body must be a JSON object")
        return value

    def validate_fields(data, allowed, required=()):
        errors = {}
        unknown = sorted(set(data) - set(allowed))
        if unknown:
            errors["unknown_fields"] = unknown
        for field in required:
            if field not in data:
                errors[field] = "is required"
        if errors:
            raise APIError(422, "validation_error", "Request validation failed", errors)

    def encode_token(user_id):
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(seconds=app.config["JWT_TTL_SECONDS"]),
        }
        return jwt.encode(payload, app.config["JWT_SECRET"], algorithm="HS256")

    def require_auth(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer ") or not header[7:]:
                raise APIError(401, "authentication_required", "A Bearer token is required")
            try:
                payload = jwt.decode(
                    header[7:], app.config["JWT_SECRET"], algorithms=["HS256"]
                )
                user_id = int(payload["sub"])
            except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
                raise APIError(401, "invalid_token", "The Bearer token is invalid or expired") from exc
            user = get_db().execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
            if user is None:
                raise APIError(401, "invalid_token", "The token user no longer exists")
            g.current_user = user
            g.audit_actor_id = user["id"]
            return view(*args, **kwargs)

        return wrapped

    @app.before_request
    def enforce_rate_limit():
        if not request.path.startswith("/api/"):
            return None
        now = time.monotonic()
        window = app.config["RATE_WINDOW_SECONDS"]
        limit = app.config["RATE_LIMIT"]
        key = request.remote_addr or "unknown"
        timestamps = [stamp for stamp in rate_buckets.get(key, []) if now - stamp < window]
        g.rate_limit = limit
        g.rate_remaining = max(0, limit - len(timestamps) - 1)
        g.rate_reset = max(0, int(window - (now - timestamps[0]))) if timestamps else window
        if len(timestamps) >= limit:
            rate_buckets[key] = timestamps
            raise APIError(429, "rate_limit_exceeded", "Too many requests; retry later")
        timestamps.append(now)
        rate_buckets[key] = timestamps
        return None

    @app.after_request
    def add_headers_and_audit(response):
        if hasattr(g, "rate_limit"):
            response.headers["X-RateLimit-Limit"] = str(g.rate_limit)
            response.headers["X-RateLimit-Remaining"] = str(g.rate_remaining)
            response.headers["X-RateLimit-Reset"] = str(g.rate_reset)
        if request.path.startswith("/api/"):
            try:
                db = get_db()
                db.execute(
                    "INSERT INTO audit_logs (actor_id, method, path, status, ip_address, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        getattr(g, "audit_actor_id", None),
                        request.method,
                        request.path,
                        response.status_code,
                        request.remote_addr or "unknown",
                        datetime.now(UTC).isoformat(),
                    ),
                )
                db.commit()
            except sqlite3.Error:
                current_app.logger.exception("Unable to write audit log")
        return response

    @app.teardown_appcontext
    def close_db(_error):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.errorhandler(APIError)
    def handle_api_error(error):
        body = {"error": {"code": error.code, "message": error.message}}
        if error.details:
            body["error"]["details"] = error.details
        response = jsonify(body)
        response.status_code = error.status
        if error.status == 429:
            response.headers["Retry-After"] = str(getattr(g, "rate_reset", 1))
        return response

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return jsonify(error={"code": error.name.lower().replace(" ", "_"), "message": error.description}), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        current_app.logger.exception("Unhandled API error", exc_info=error)
        return jsonify(error={"code": "internal_error", "message": "An unexpected error occurred"}), 500

    @app.post("/api/v1/auth/register")
    def register():
        data = json_body()
        validate_fields(data, {"email", "password"}, {"email", "password"})
        email = data.get("email")
        password = data.get("password")
        errors = {}
        if not isinstance(email, str) or not EMAIL_PATTERN.fullmatch(email.strip()):
            errors["email"] = "must be a valid email address"
        if not isinstance(password, str) or len(password) < 8:
            errors["password"] = "must contain at least 8 characters"
        if errors:
            raise APIError(422, "validation_error", "Request validation failed", errors)
        now = datetime.now(UTC).isoformat()
        try:
            cursor = get_db().execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email.strip().lower(), generate_password_hash(password), now),
            )
            get_db().commit()
        except sqlite3.IntegrityError as exc:
            raise APIError(409, "email_exists", "An account with this email already exists") from exc
        return jsonify(data={"id": cursor.lastrowid, "email": email.strip().lower()}), 201

    @app.post("/api/v1/auth/login")
    def login():
        data = json_body()
        validate_fields(data, {"email", "password"}, {"email", "password"})
        email, password = data.get("email"), data.get("password")
        if not isinstance(email, str) or not isinstance(password, str):
            raise APIError(422, "validation_error", "Email and password must be strings")
        user = get_db().execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            raise APIError(401, "invalid_credentials", "Email or password is incorrect")
        g.audit_actor_id = user["id"]
        return jsonify(data={"access_token": encode_token(user["id"]), "token_type": "Bearer", "expires_in": app.config["JWT_TTL_SECONDS"]})

    def item_json(row):
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def validate_item(data, partial=False):
        validate_fields(data, {"name", "description"}, () if partial else {"name"})
        errors = {}
        if "name" in data and (not isinstance(data["name"], str) or not data["name"].strip() or len(data["name"]) > 120):
            errors["name"] = "must be a non-empty string of at most 120 characters"
        if "description" in data and (not isinstance(data["description"], str) or len(data["description"]) > 2000):
            errors["description"] = "must be a string of at most 2000 characters"
        if partial and not data:
            errors["body"] = "must contain at least one field"
        if errors:
            raise APIError(422, "validation_error", "Request validation failed", errors)

    @app.get("/api/v1/items")
    @require_auth
    def list_items():
        try:
            page = int(request.args.get("page", 1))
            per_page = int(request.args.get("per_page", 20))
        except ValueError as exc:
            raise APIError(422, "validation_error", "page and per_page must be integers") from exc
        if page < 1 or per_page < 1 or per_page > app.config["MAX_PAGE_SIZE"]:
            raise APIError(422, "validation_error", f"page must be positive and per_page must be between 1 and {app.config['MAX_PAGE_SIZE']}")
        db = get_db()
        total = db.execute("SELECT COUNT(*) FROM items WHERE owner_id = ?", (g.current_user["id"],)).fetchone()[0]
        rows = db.execute(
            "SELECT * FROM items WHERE owner_id = ? ORDER BY id LIMIT ? OFFSET ?",
            (g.current_user["id"], per_page, (page - 1) * per_page),
        ).fetchall()
        pages = (total + per_page - 1) // per_page
        return jsonify(data=[item_json(row) for row in rows], pagination={"page": page, "per_page": per_page, "total": total, "pages": pages})

    @app.post("/api/v1/items")
    @require_auth
    def create_item():
        data = json_body()
        validate_item(data)
        now = datetime.now(UTC).isoformat()
        cursor = get_db().execute(
            "INSERT INTO items (owner_id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (g.current_user["id"], data["name"].strip(), data.get("description", ""), now, now),
        )
        get_db().commit()
        row = get_db().execute("SELECT * FROM items WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(data=item_json(row)), 201

    def owned_item(item_id):
        row = get_db().execute(
            "SELECT * FROM items WHERE id = ? AND owner_id = ?", (item_id, g.current_user["id"])
        ).fetchone()
        if row is None:
            raise APIError(404, "not_found", "Item not found")
        return row

    @app.get("/api/v1/items/<int:item_id>")
    @require_auth
    def get_item(item_id):
        return jsonify(data=item_json(owned_item(item_id)))

    @app.patch("/api/v1/items/<int:item_id>")
    @require_auth
    def update_item(item_id):
        row = owned_item(item_id)
        data = json_body()
        validate_item(data, partial=True)
        name = data.get("name", row["name"])
        if "name" in data:
            name = name.strip()
        description = data.get("description", row["description"])
        get_db().execute(
            "UPDATE items SET name = ?, description = ?, updated_at = ? WHERE id = ?",
            (name, description, datetime.now(UTC).isoformat(), item_id),
        )
        get_db().commit()
        return jsonify(data=item_json(get_db().execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()))

    @app.delete("/api/v1/items/<int:item_id>")
    @require_auth
    def delete_item(item_id):
        owned_item(item_id)
        get_db().execute("DELETE FROM items WHERE id = ?", (item_id,))
        get_db().commit()
        return "", 204

    @app.get("/api/v1/audit-logs")
    @require_auth
    def audit_logs():
        rows = get_db().execute(
            "SELECT id, method, path, status, ip_address, created_at FROM audit_logs "
            "WHERE actor_id = ? ORDER BY id DESC LIMIT 100",
            (g.current_user["id"],),
        ).fetchall()
        return jsonify(data=[dict(row) for row in rows])

    return app


if __name__ == "__main__":
    create_app().run()
