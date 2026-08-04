import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("DATABASE", "api.db"),
        JWT_SECRET=os.environ.get("JWT_SECRET", "change-me-in-production"),
        JWT_TTL_SECONDS=3600,
        RATE_LIMIT=100,
        RATE_WINDOW_SECONDS=60,
        MAX_PAGE_SIZE=100,
    )
    if test_config:
        app.config.update(test_config)

    app.extensions["rate_limits"] = {}

    @app.before_request
    def enforce_rate_limit():
        now = time.time()
        key = request.remote_addr or "unknown"
        window, count = app.extensions["rate_limits"].get(key, (now, 0))
        if now - window >= app.config["RATE_WINDOW_SECONDS"]:
            window, count = now, 0
        count += 1
        app.extensions["rate_limits"][key] = (window, count)
        remaining = max(0, app.config["RATE_LIMIT"] - count)
        g.rate_headers = {
            "X-RateLimit-Limit": str(app.config["RATE_LIMIT"]),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(window + app.config["RATE_WINDOW_SECONDS"])),
        }
        if count > app.config["RATE_LIMIT"]:
            return error_response("rate_limit_exceeded", "Too many requests", 429)

    @app.after_request
    def add_response_headers(response):
        for name, value in getattr(g, "rate_headers", {}).items():
            response.headers[name] = value
        response.headers["X-API-Version"] = "1"
        return response

    @app.teardown_appcontext
    def close_database(_error=None):
        database = g.pop("database", None)
        if database is not None:
            database.close()

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return error_response(error.name.lower().replace(" ", "_"), error.description, error.code)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        current_app.logger.exception("Unhandled API error", exc_info=error)
        return error_response("internal_server_error", "An unexpected error occurred", 500)

    @app.post("/api/v1/auth/register")
    def register():
        data, validation_error = validate_json(
            {"username": (str, 3, 50), "password": (str, 8, 128)}
        )
        if validation_error:
            return validation_error
        database = get_db()
        try:
            cursor = database.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (data["username"], generate_password_hash(data["password"])),
            )
            database.commit()
        except sqlite3.IntegrityError:
            return error_response("conflict", "Username already exists", 409)
        audit(cursor.lastrowid, "user.register", "user", cursor.lastrowid)
        return jsonify({"id": cursor.lastrowid, "username": data["username"]}), 201

    @app.post("/api/v1/auth/login")
    def login():
        data, validation_error = validate_json(
            {"username": (str, 1, 50), "password": (str, 1, 128)}
        )
        if validation_error:
            return validation_error
        user = get_db().execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (data["username"],)
        ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], data["password"]):
            return error_response("invalid_credentials", "Invalid username or password", 401)
        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": str(user["id"]),
                "iat": now,
                "exp": now + timedelta(seconds=app.config["JWT_TTL_SECONDS"]),
            },
            app.config["JWT_SECRET"],
            algorithm="HS256",
        )
        audit(user["id"], "user.login", "user", user["id"])
        return jsonify({"access_token": token, "token_type": "Bearer", "expires_in": app.config["JWT_TTL_SECONDS"]})

    @app.get("/api/v1/items")
    @authenticated
    def list_items():
        page, per_page, pagination_error = parse_pagination()
        if pagination_error:
            return pagination_error
        database = get_db()
        total = database.execute(
            "SELECT COUNT(*) FROM items WHERE user_id = ?", (g.user_id,)
        ).fetchone()[0]
        rows = database.execute(
            "SELECT id, name, description, created_at, updated_at FROM items "
            "WHERE user_id = ? ORDER BY id LIMIT ? OFFSET ?",
            (g.user_id, per_page, (page - 1) * per_page),
        ).fetchall()
        return jsonify({
            "data": [dict(row) for row in rows],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page,
            },
        })

    @app.post("/api/v1/items")
    @authenticated
    def create_item():
        data, validation_error = validate_json(
            {"name": (str, 1, 100), "description": (str, 0, 1000)},
            optional={"description"},
        )
        if validation_error:
            return validation_error
        now = iso_now()
        cursor = get_db().execute(
            "INSERT INTO items (user_id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (g.user_id, data["name"], data.get("description", ""), now, now),
        )
        get_db().commit()
        audit(g.user_id, "item.create", "item", cursor.lastrowid)
        item = get_db().execute(
            "SELECT id, name, description, created_at, updated_at FROM items WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return jsonify(dict(item)), 201

    @app.get("/api/v1/items/<int:item_id>")
    @authenticated
    def get_item(item_id):
        item = find_item(item_id)
        if item is None:
            return error_response("not_found", "Item not found", 404)
        return jsonify(dict(item))

    @app.patch("/api/v1/items/<int:item_id>")
    @authenticated
    def update_item(item_id):
        item = find_item(item_id)
        if item is None:
            return error_response("not_found", "Item not found", 404)
        data, validation_error = validate_json(
            {"name": (str, 1, 100), "description": (str, 0, 1000)},
            optional={"name", "description"},
            require_one=True,
        )
        if validation_error:
            return validation_error
        name = data.get("name", item["name"])
        description = data.get("description", item["description"])
        get_db().execute(
            "UPDATE items SET name = ?, description = ?, updated_at = ? WHERE id = ?",
            (name, description, iso_now(), item_id),
        )
        get_db().commit()
        audit(g.user_id, "item.update", "item", item_id)
        return jsonify(dict(find_item(item_id)))

    @app.delete("/api/v1/items/<int:item_id>")
    @authenticated
    def delete_item(item_id):
        if find_item(item_id) is None:
            return error_response("not_found", "Item not found", 404)
        get_db().execute("DELETE FROM items WHERE id = ?", (item_id,))
        get_db().commit()
        audit(g.user_id, "item.delete", "item", item_id)
        return "", 204

    @app.get("/api/v1/audit-logs")
    @authenticated
    def list_audit_logs():
        page, per_page, pagination_error = parse_pagination()
        if pagination_error:
            return pagination_error
        database = get_db()
        total = database.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE user_id = ?", (g.user_id,)
        ).fetchone()[0]
        rows = database.execute(
            "SELECT id, action, resource_type, resource_id, created_at, ip_address "
            "FROM audit_logs WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (g.user_id, per_page, (page - 1) * per_page),
        ).fetchall()
        return jsonify({
            "data": [dict(row) for row in rows],
            "pagination": {"page": page, "per_page": per_page, "total": total,
                           "pages": (total + per_page - 1) // per_page},
        })

    with app.app_context():
        init_db()
    return app


def get_db():
    if "database" not in g:
        g.database = sqlite3.connect(current_app.config["DATABASE"])
        g.database.row_factory = sqlite3.Row
        g.database.execute("PRAGMA foreign_keys = ON")
    return g.database


def init_db():
    get_db().executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
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
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id INTEGER,
            created_at TEXT NOT NULL,
            ip_address TEXT
        );
        """
    )
    get_db().commit()


def authenticated(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return error_response("unauthorized", "A Bearer token is required", 401)
        try:
            payload = jwt.decode(
                header[7:], current_app.config["JWT_SECRET"], algorithms=["HS256"]
            )
            g.user_id = int(payload["sub"])
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            return error_response("unauthorized", "Token is invalid or expired", 401)
        if get_db().execute("SELECT 1 FROM users WHERE id = ?", (g.user_id,)).fetchone() is None:
            return error_response("unauthorized", "Token user no longer exists", 401)
        return view(*args, **kwargs)
    return wrapped


def validate_json(fields, optional=None, require_one=False):
    optional = optional or set()
    if not request.is_json:
        return None, error_response("validation_error", "Content-Type must be application/json", 400)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, error_response("validation_error", "Request body must be a JSON object", 400)
    errors = {}
    unknown = set(data) - set(fields)
    if unknown:
        errors["body"] = "Unknown fields: " + ", ".join(sorted(unknown))
    for name, (expected_type, minimum, maximum) in fields.items():
        if name not in data:
            if name not in optional:
                errors[name] = "This field is required"
            continue
        value = data[name]
        if not isinstance(value, expected_type):
            errors[name] = "Must be a string"
        elif not minimum <= len(value.strip()) <= maximum:
            errors[name] = f"Length must be between {minimum} and {maximum}"
        else:
            data[name] = value.strip() if minimum else value
    if require_one and not (set(data) & set(fields)):
        errors["body"] = "At least one field is required"
    if errors:
        return None, error_response("validation_error", "Invalid request", 400, errors)
    return data, None


def parse_pagination():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return None, None, error_response("validation_error", "Pagination values must be integers", 400)
    if page < 1 or per_page < 1 or per_page > current_app.config["MAX_PAGE_SIZE"]:
        return None, None, error_response(
            "validation_error",
            f"page must be positive and per_page must be between 1 and {current_app.config['MAX_PAGE_SIZE']}",
            400,
        )
    return page, per_page, None


def find_item(item_id):
    return get_db().execute(
        "SELECT id, name, description, created_at, updated_at FROM items WHERE id = ? AND user_id = ?",
        (item_id, g.user_id),
    ).fetchone()


def audit(user_id, action, resource_type, resource_id):
    get_db().execute(
        "INSERT INTO audit_logs (user_id, action, resource_type, resource_id, created_at, ip_address) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, action, resource_type, resource_id, iso_now(), request.remote_addr),
    )
    get_db().commit()


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def error_response(code, message, status, details=None):
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return jsonify(body), status
