from __future__ import annotations

import json
import logging
import math
import re
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any

import jwt
from flask import Blueprint, Flask, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash


USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def error_response(code: str, message: str, status: int, details: dict | None = None):
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return jsonify({"error": error}), status


def require_json() -> tuple[dict | None, Any | None]:
    if not request.is_json:
        return None, error_response(
            "validation_error", "Request body must be JSON", 400
        )
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, error_response(
            "validation_error", "Request body must be a JSON object", 400
        )
    return data, None


def issue_token(username: str) -> str:
    now = utc_now()
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(seconds=current_app.config["JWT_EXPIRES_SECONDS"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def authenticated(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return error_response(
                "authentication_required", "A Bearer token is required", 401
            )
        token = header.removeprefix("Bearer ").strip()
        try:
            claims = jwt.decode(
                token, current_app.config["JWT_SECRET"], algorithms=["HS256"]
            )
        except jwt.ExpiredSignatureError:
            return error_response("token_expired", "The token has expired", 401)
        except jwt.InvalidTokenError:
            return error_response("invalid_token", "The token is invalid", 401)

        username = claims.get("sub")
        if not isinstance(username, str) or username not in current_app.extensions["users"]:
            return error_response("invalid_token", "The token is invalid", 401)
        g.username = username
        return view(*args, **kwargs)

    return wrapped


def create_api_blueprint() -> Blueprint:
    api = Blueprint("api_v1", __name__, url_prefix="/api/v1")

    @api.post("/auth/register")
    def register():
        data, error = require_json()
        if error:
            return error
        username = data.get("username")
        password = data.get("password")
        details = {}
        if not isinstance(username, str) or not USERNAME_RE.fullmatch(username):
            details["username"] = (
                "Must be 3-50 characters using letters, numbers, '.', '_', or '-'"
            )
        if not isinstance(password, str) or len(password) < 8:
            details["password"] = "Must be at least 8 characters"
        if details:
            return error_response("validation_error", "Invalid input", 400, details)

        users = current_app.extensions["users"]
        if username in users:
            return error_response("conflict", "Username is already registered", 409)
        users[username] = {"password_hash": generate_password_hash(password)}
        return jsonify({"username": username}), 201

    @api.post("/auth/login")
    def login():
        data, error = require_json()
        if error:
            return error
        username = data.get("username")
        password = data.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            return error_response("validation_error", "Username and password are required", 400)

        user = current_app.extensions["users"].get(username)
        if not user or not check_password_hash(user["password_hash"], password):
            return error_response("invalid_credentials", "Invalid credentials", 401)
        return jsonify(
            {
                "access_token": issue_token(username),
                "token_type": "Bearer",
                "expires_in": current_app.config["JWT_EXPIRES_SECONDS"],
            }
        )

    @api.get("/items")
    @authenticated
    def list_items():
        try:
            page = int(request.args.get("page", 1))
            per_page = int(request.args.get("per_page", 20))
        except ValueError:
            return error_response("validation_error", "Pagination values must be integers", 400)
        if page < 1 or not 1 <= per_page <= 100:
            return error_response(
                "validation_error", "page must be >= 1 and per_page must be 1-100", 400
            )

        owned = [
            item
            for item in current_app.extensions["items"].values()
            if item["owner"] == g.username
        ]
        owned.sort(key=lambda item: item["created_at"])
        total = len(owned)
        start = (page - 1) * per_page
        return jsonify(
            {
                "data": owned[start : start + per_page],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": math.ceil(total / per_page),
                },
            }
        )

    @api.post("/items")
    @authenticated
    def create_item():
        data, error = require_json()
        if error:
            return error
        title = data.get("title")
        description = data.get("description", "")
        details = {}
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            details["title"] = "Must be a non-empty string of at most 200 characters"
        if not isinstance(description, str) or len(description) > 2000:
            details["description"] = "Must be a string of at most 2000 characters"
        if details:
            return error_response("validation_error", "Invalid input", 400, details)

        item_id = str(uuid.uuid4())
        now = timestamp()
        item = {
            "id": item_id,
            "title": title.strip(),
            "description": description,
            "owner": g.username,
            "created_at": now,
            "updated_at": now,
        }
        current_app.extensions["items"][item_id] = item
        return jsonify(item), 201

    def find_owned_item(item_id: str):
        item = current_app.extensions["items"].get(item_id)
        if not item or item["owner"] != g.username:
            return None
        return item

    @api.get("/items/<item_id>")
    @authenticated
    def get_item(item_id: str):
        item = find_owned_item(item_id)
        if not item:
            return error_response("not_found", "Item not found", 404)
        return jsonify(item)

    @api.patch("/items/<item_id>")
    @authenticated
    def update_item(item_id: str):
        item = find_owned_item(item_id)
        if not item:
            return error_response("not_found", "Item not found", 404)
        data, error = require_json()
        if error:
            return error
        unknown = set(data) - {"title", "description"}
        details = {}
        if unknown:
            details["unknown_fields"] = sorted(unknown)
        if "title" in data and (
            not isinstance(data["title"], str)
            or not data["title"].strip()
            or len(data["title"]) > 200
        ):
            details["title"] = "Must be a non-empty string of at most 200 characters"
        if "description" in data and (
            not isinstance(data["description"], str)
            or len(data["description"]) > 2000
        ):
            details["description"] = "Must be a string of at most 2000 characters"
        if not data:
            details["body"] = "At least one field is required"
        if details:
            return error_response("validation_error", "Invalid input", 400, details)
        if "title" in data:
            item["title"] = data["title"].strip()
        if "description" in data:
            item["description"] = data["description"]
        item["updated_at"] = timestamp()
        return jsonify(item)

    @api.delete("/items/<item_id>")
    @authenticated
    def delete_item(item_id: str):
        item = find_owned_item(item_id)
        if not item:
            return error_response("not_found", "Item not found", 404)
        del current_app.extensions["items"][item_id]
        return "", 204

    return api


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        JWT_SECRET="change-this-secret-in-production",
        JWT_EXPIRES_SECONDS=900,
        RATE_LIMIT=100,
        RATE_WINDOW_SECONDS=60,
    )
    if config:
        app.config.update(config)

    app.extensions["users"] = {}
    app.extensions["items"] = {}
    app.extensions["rate_buckets"] = defaultdict(deque)
    app.extensions["audit_events"] = []
    audit_logger = logging.getLogger("api.audit")

    @app.before_request
    def enforce_rate_limit():
        now = time.monotonic()
        window = app.config["RATE_WINDOW_SECONDS"]
        limit = app.config["RATE_LIMIT"]
        key = request.remote_addr or "unknown"
        bucket = app.extensions["rate_buckets"][key]
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        remaining = max(0, limit - len(bucket) - 1)
        g.rate_limit = (limit, remaining, int(window))
        if len(bucket) >= limit:
            retry_after = max(1, math.ceil(window - (now - bucket[0])))
            g.rate_limit = (limit, 0, retry_after)
            response, status = error_response(
                "rate_limit_exceeded", "Too many requests", 429
            )
            response.headers["Retry-After"] = str(retry_after)
            return response, status
        bucket.append(now)

    @app.after_request
    def add_headers_and_audit(response):
        limit, remaining, reset = getattr(
            g,
            "rate_limit",
            (app.config["RATE_LIMIT"], app.config["RATE_LIMIT"], 0),
        )
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset)
        event = {
            "timestamp": timestamp(),
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "actor": getattr(g, "username", None),
            "remote_addr": request.remote_addr,
        }
        app.extensions["audit_events"].append(event)
        audit_logger.info(json.dumps(event, separators=(",", ":")))
        return response

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        code = "not_found" if error.code == 404 else "http_error"
        return error_response(code, error.description, error.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled request error", exc_info=error)
        return error_response("internal_error", "An internal error occurred", 500)

    app.register_blueprint(create_api_blueprint())
    return app
