from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable
from uuid import uuid4

import jwt
from flask import Blueprint, Flask, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash


def create_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        JWT_SECRET="change-me-in-production",
        JWT_TTL_SECONDS=3600,
        RATE_LIMIT=100,
        RATE_WINDOW_SECONDS=60,
    )
    if config:
        app.config.update(config)

    app.extensions["users"] = {}
    app.extensions["items"] = {}
    app.extensions["audit_log"] = []
    app.extensions["rate_buckets"] = defaultdict(deque)
    app.register_blueprint(api)
    register_hooks(app)
    return app


api = Blueprint("api_v1", __name__, url_prefix="/api/v1")


def error_response(status: int, code: str, message: str, details: Any = None):
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return jsonify(body), status


def register_hooks(app: Flask) -> None:
    @app.before_request
    def rate_limit():
        if not request.path.startswith("/api/"):
            return None
        limit = app.config["RATE_LIMIT"]
        window = app.config["RATE_WINDOW_SECONDS"]
        now = time.monotonic()
        key = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
        bucket = app.extensions["rate_buckets"][key]
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        if len(bucket) >= limit:
            response, status = error_response(429, "rate_limit_exceeded", "Too many requests")
            response.headers["Retry-After"] = str(max(1, int(window - (now - bucket[0]))))
            return response, status
        bucket.append(now)
        return None

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        return error_response(exc.code or 500, exc.name.lower().replace(" ", "_"), exc.description)

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        app.logger.exception("Unhandled API error", exc_info=exc)
        return error_response(500, "internal_server_error", "An unexpected error occurred")


def audit(action: str, outcome: str = "success", resource_id: str | None = None) -> None:
    current_app.extensions["audit_log"].append(
        {
            "id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": getattr(g, "user", {}).get("username"),
            "action": action,
            "outcome": outcome,
            "resource_id": resource_id,
            "ip": request.remote_addr,
        }
    )


def issue_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(seconds=current_app.config["JWT_TTL_SECONDS"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def authenticated(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return error_response(401, "authentication_required", "A bearer token is required")
        try:
            payload = jwt.decode(
                header[7:], current_app.config["JWT_SECRET"], algorithms=["HS256"]
            )
        except jwt.ExpiredSignatureError:
            return error_response(401, "token_expired", "The bearer token has expired")
        except jwt.InvalidTokenError:
            return error_response(401, "invalid_token", "The bearer token is invalid")
        user = current_app.extensions["users"].get(payload.get("sub"))
        if user is None:
            return error_response(401, "invalid_token", "The token user no longer exists")
        g.user = user
        return view(*args, **kwargs)

    return wrapped


def json_object() -> tuple[dict[str, Any] | None, Any | None]:
    if not request.is_json:
        return None, error_response(415, "unsupported_media_type", "Content-Type must be application/json")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, error_response(400, "invalid_json", "Request body must be a JSON object")
    return data, None


def validate_credentials(data: dict[str, Any]) -> dict[str, str]:
    errors = {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not 3 <= len(username.strip()) <= 50:
        errors["username"] = "must be a string between 3 and 50 characters"
    if not isinstance(password, str) or len(password) < 8:
        errors["password"] = "must be a string of at least 8 characters"
    return errors


@api.post("/auth/register")
def register():
    data, invalid = json_object()
    if invalid:
        return invalid
    errors = validate_credentials(data)
    if errors:
        return error_response(422, "validation_error", "Request validation failed", errors)
    username = data["username"].strip()
    users = current_app.extensions["users"]
    if username in users:
        return error_response(409, "username_exists", "Username is already registered")
    users[username] = {"username": username, "password_hash": generate_password_hash(data["password"])}
    g.user = users[username]
    audit("user.register")
    return jsonify({"data": {"username": username}}), 201


@api.post("/auth/login")
def login():
    data, invalid = json_object()
    if invalid:
        return invalid
    errors = validate_credentials(data)
    if errors:
        return error_response(422, "validation_error", "Request validation failed", errors)
    user = current_app.extensions["users"].get(data["username"].strip())
    if user is None or not check_password_hash(user["password_hash"], data["password"]):
        audit("user.login", "failure")
        return error_response(401, "invalid_credentials", "Invalid username or password")
    g.user = user
    audit("user.login")
    return jsonify({"data": {"access_token": issue_token(user["username"]), "token_type": "Bearer"}})


@api.get("/items")
@authenticated
def list_items():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return error_response(422, "validation_error", "Pagination values must be integers")
    if page < 1 or not 1 <= per_page <= 100:
        return error_response(422, "validation_error", "page must be positive and per_page must be 1-100")
    items = list(current_app.extensions["items"].values())
    start = (page - 1) * per_page
    return jsonify(
        {
            "data": items[start : start + per_page],
            "meta": {"page": page, "per_page": per_page, "total": len(items)},
        }
    )


@api.post("/items")
@authenticated
def create_item():
    data, invalid = json_object()
    if invalid:
        return invalid
    errors = {}
    if not isinstance(data.get("name"), str) or not 1 <= len(data["name"].strip()) <= 100:
        errors["name"] = "must be a non-empty string of at most 100 characters"
    if "description" in data and not isinstance(data["description"], str):
        errors["description"] = "must be a string"
    if errors:
        return error_response(422, "validation_error", "Request validation failed", errors)
    item_id = str(uuid4())
    item = {
        "id": item_id,
        "name": data["name"].strip(),
        "description": data.get("description", ""),
        "owner": g.user["username"],
    }
    current_app.extensions["items"][item_id] = item
    audit("item.create", resource_id=item_id)
    return jsonify({"data": item}), 201


@api.get("/items/<item_id>")
@authenticated
def get_item(item_id: str):
    item = current_app.extensions["items"].get(item_id)
    if item is None:
        return error_response(404, "item_not_found", "Item not found")
    return jsonify({"data": item})


@api.delete("/items/<item_id>")
@authenticated
def delete_item(item_id: str):
    item = current_app.extensions["items"].get(item_id)
    if item is None:
        return error_response(404, "item_not_found", "Item not found")
    if item["owner"] != g.user["username"]:
        return error_response(403, "forbidden", "Only the item owner may delete it")
    del current_app.extensions["items"][item_id]
    audit("item.delete", resource_id=item_id)
    return "", 204


@api.get("/audit-logs")
@authenticated
def audit_logs():
    records = current_app.extensions["audit_log"]
    return jsonify({"data": records, "meta": {"total": len(records)}})
