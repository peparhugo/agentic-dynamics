from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any

import jwt
from flask import Flask, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


class RateLimiter:
    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window: int) -> tuple[int, int]:
        now = time.time()
        with self._lock:
            timestamps = [stamp for stamp in self._requests.get(key, []) if stamp > now - window]
            if len(timestamps) >= limit:
                retry_after = max(1, int(window - (now - timestamps[0])) + 1)
                self._requests[key] = timestamps
                raise ApiError(429, "rate_limit_exceeded", "Too many requests", {"retry_after": retry_after})
            timestamps.append(now)
            self._requests[key] = timestamps
            return limit - len(timestamps), int(now + window)


def create_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(Path(app.instance_path) / "api.sqlite"),
        JWT_SECRET=os.environ.get("JWT_SECRET", "change-this-secret-in-production"),
        JWT_TTL_SECONDS=3600,
        RATE_LIMIT=100,
        RATE_LIMIT_WINDOW=60,
        TESTING=False,
    )
    if config:
        app.config.update(config)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    app.extensions["rate_limiter"] = RateLimiter()

    app.teardown_appcontext(close_db)
    app.before_request(apply_rate_limit)
    app.after_request(add_response_metadata)
    register_error_handlers(app)
    register_routes(app)

    with app.app_context():
        init_db()
    return app


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    get_db().executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
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
            user_id INTEGER,
            action TEXT NOT NULL,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            status INTEGER NOT NULL,
            ip_address TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    get_db().commit()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def apply_rate_limit() -> None:
    if not request.path.startswith("/api/"):
        return
    identity = request.headers.get("Authorization") or request.remote_addr or "unknown"
    remaining, reset = current_app.extensions["rate_limiter"].check(
        identity, current_app.config["RATE_LIMIT"], current_app.config["RATE_LIMIT_WINDOW"]
    )
    g.rate_limit_remaining = remaining
    g.rate_limit_reset = reset


def add_response_metadata(response):
    response.headers["X-API-Version"] = "1"
    if hasattr(g, "rate_limit_remaining"):
        response.headers["X-RateLimit-Limit"] = str(current_app.config["RATE_LIMIT"])
        response.headers["X-RateLimit-Remaining"] = str(g.rate_limit_remaining)
        response.headers["X-RateLimit-Reset"] = str(g.rate_limit_reset)
    if request.path.startswith("/api/"):
        try:
            db = get_db()
            db.execute(
                "INSERT INTO audit_logs (user_id, action, method, path, status, ip_address, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    getattr(g, "user_id", None),
                    request.endpoint or "unknown",
                    request.method,
                    request.path,
                    response.status_code,
                    request.remote_addr or "unknown",
                    utc_now(),
                ),
            )
            db.commit()
        except sqlite3.Error:
            current_app.logger.exception("Failed to write audit log")
    return response


def error_response(status: int, code: str, message: str, details: dict | None = None):
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return jsonify({"error": error}), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        response, status = error_response(error.status, error.code, error.message, error.details)
        if error.status == 429 and error.details:
            response.headers["Retry-After"] = str(error.details["retry_after"])
        return response, status

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        return error_response(error.code or 500, error.name.lower().replace(" ", "_"), error.description)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        app.logger.exception("Unhandled API error", exc_info=error)
        return error_response(500, "internal_server_error", "An unexpected error occurred")


def json_body(required: set[str], optional: set[str] | None = None) -> dict[str, Any]:
    optional = optional or set()
    if not request.is_json:
        raise ApiError(415, "unsupported_media_type", "Content-Type must be application/json")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "invalid_json", "Request body must be a JSON object")
    errors: dict[str, str] = {}
    for field in required - data.keys():
        errors[field] = "is required"
    for field in data.keys() - required - optional:
        errors[field] = "is not allowed"
    if errors:
        raise ApiError(422, "validation_error", "Request validation failed", errors)
    return data


def validate_text(data: dict, field: str, minimum: int, maximum: int, required: bool = True) -> str | None:
    value = data.get(field)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ApiError(
            422,
            "validation_error",
            "Request validation failed",
            {field: f"must be a string between {minimum} and {maximum} characters"},
        )
    return value.strip()


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise ApiError(401, "authentication_required", "A bearer token is required")
        try:
            payload = jwt.decode(
                token,
                current_app.config["JWT_SECRET"],
                algorithms=["HS256"],
                options={"require": ["exp", "iat", "sub", "jti"]},
            )
            g.user_id = int(payload["sub"])
        except (jwt.PyJWTError, ValueError, TypeError):
            raise ApiError(401, "invalid_token", "The bearer token is invalid or expired") from None
        if get_db().execute("SELECT 1 FROM users WHERE id = ?", (g.user_id,)).fetchone() is None:
            raise ApiError(401, "invalid_token", "The bearer token is invalid or expired")
        return view(*args, **kwargs)

    return wrapped


def item_json(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def owned_item(item_id: int) -> sqlite3.Row:
    row = get_db().execute(
        "SELECT * FROM items WHERE id = ? AND owner_id = ?", (item_id, g.user_id)
    ).fetchone()
    if row is None:
        raise ApiError(404, "not_found", "Item not found")
    return row


def pagination() -> tuple[int, int]:
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        raise ApiError(422, "validation_error", "Pagination values must be integers") from None
    if page < 1 or not 1 <= per_page <= 100:
        raise ApiError(422, "validation_error", "page must be positive and per_page must be between 1 and 100")
    return page, per_page


def register_routes(app: Flask) -> None:
    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.post("/api/v1/auth/register")
    def register():
        data = json_body({"email", "password"})
        email = validate_text(data, "email", 3, 254).lower()
        password = validate_text(data, "password", 8, 128)
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            raise ApiError(422, "validation_error", "Request validation failed", {"email": "must be valid"})
        try:
            cursor = get_db().execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email, generate_password_hash(password), utc_now()),
            )
            get_db().commit()
        except sqlite3.IntegrityError:
            raise ApiError(409, "email_exists", "An account with this email already exists") from None
        g.user_id = cursor.lastrowid
        return jsonify({"id": cursor.lastrowid, "email": email}), 201

    @app.post("/api/v1/auth/login")
    def login():
        data = json_body({"email", "password"})
        email = validate_text(data, "email", 3, 254).lower()
        password = validate_text(data, "password", 1, 128)
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            raise ApiError(401, "invalid_credentials", "Email or password is incorrect")
        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": str(user["id"]),
                "iat": now,
                "exp": now + timedelta(seconds=current_app.config["JWT_TTL_SECONDS"]),
                "jti": str(uuid.uuid4()),
            },
            current_app.config["JWT_SECRET"],
            algorithm="HS256",
        )
        g.user_id = user["id"]
        return jsonify({"access_token": token, "token_type": "Bearer", "expires_in": current_app.config["JWT_TTL_SECONDS"]})

    @app.get("/api/v1/items")
    @require_auth
    def list_items():
        page, per_page = pagination()
        db = get_db()
        total = db.execute("SELECT COUNT(*) FROM items WHERE owner_id = ?", (g.user_id,)).fetchone()[0]
        rows = db.execute(
            "SELECT * FROM items WHERE owner_id = ? ORDER BY id LIMIT ? OFFSET ?",
            (g.user_id, per_page, (page - 1) * per_page),
        ).fetchall()
        pages = (total + per_page - 1) // per_page
        return jsonify({"data": [item_json(row) for row in rows], "pagination": {"page": page, "per_page": per_page, "total": total, "pages": pages}})

    @app.post("/api/v1/items")
    @require_auth
    def create_item():
        data = json_body({"name"}, {"description"})
        name = validate_text(data, "name", 1, 100)
        description = validate_text(data, "description", 0, 1000, required=False) or ""
        now = utc_now()
        cursor = get_db().execute(
            "INSERT INTO items (owner_id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (g.user_id, name, description, now, now),
        )
        get_db().commit()
        return jsonify(item_json(owned_item(cursor.lastrowid))), 201

    @app.get("/api/v1/items/<int:item_id>")
    @require_auth
    def get_item(item_id: int):
        return jsonify(item_json(owned_item(item_id)))

    @app.patch("/api/v1/items/<int:item_id>")
    @require_auth
    def update_item(item_id: int):
        item = owned_item(item_id)
        data = json_body(set(), {"name", "description"})
        if not data:
            raise ApiError(422, "validation_error", "At least one field is required")
        name = validate_text(data, "name", 1, 100, required=False) or item["name"]
        description = validate_text(data, "description", 0, 1000, required=False)
        if description is None:
            description = item["description"]
        get_db().execute(
            "UPDATE items SET name = ?, description = ?, updated_at = ? WHERE id = ?",
            (name, description, utc_now(), item_id),
        )
        get_db().commit()
        return jsonify(item_json(owned_item(item_id)))

    @app.delete("/api/v1/items/<int:item_id>")
    @require_auth
    def delete_item(item_id: int):
        owned_item(item_id)
        get_db().execute("DELETE FROM items WHERE id = ?", (item_id,))
        get_db().commit()
        return "", 204


app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run()
