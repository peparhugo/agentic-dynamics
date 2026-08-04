import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import wraps
from itertools import count

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


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        JWT_SECRET="change-this-secret-in-production",
        JWT_TTL_SECONDS=3600,
        RATE_LIMIT=100,
        RATE_WINDOW_SECONDS=60,
        MAX_PAGE_SIZE=100,
    )
    if config:
        app.config.update(config)

    app.users = {}
    app.items = {}
    app.audit_events = []
    app.rate_buckets = defaultdict(deque)
    app.item_ids = count(1)

    @app.before_request
    def enforce_rate_limit():
        limit = app.config["RATE_LIMIT"]
        if limit <= 0:
            return None
        now = time.monotonic()
        window = app.config["RATE_WINDOW_SECONDS"]
        key = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
        bucket = app.rate_buckets[key]
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(1, int(window - (now - bucket[0]) + 0.999))
            response = error_response(429, "rate_limit_exceeded", "Too many requests")
            response.headers["Retry-After"] = str(retry_after)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = "0"
            return response
        bucket.append(now)
        g.rate_limit_remaining = limit - len(bucket)

    @app.after_request
    def add_response_headers(response):
        response.headers["X-API-Version"] = "1"
        if hasattr(g, "rate_limit_remaining"):
            response.headers["X-RateLimit-Limit"] = str(app.config["RATE_LIMIT"])
            response.headers["X-RateLimit-Remaining"] = str(g.rate_limit_remaining)
        return response

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return error_response(error.status, error.code, error.message, error.details)

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        code = error.name.lower().replace(" ", "_")
        return error_response(error.code, code, error.description)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled API error")
        return error_response(500, "internal_server_error", "An unexpected error occurred")

    @app.post("/api/v1/auth/register")
    def register():
        data = json_body()
        errors = validate_fields(data, required={"username", "password"}, allowed={"username", "password"})
        username = data.get("username")
        password = data.get("password")
        if isinstance(username, str) and not 3 <= len(username.strip()) <= 50:
            errors["username"] = "must be between 3 and 50 characters"
        if isinstance(password, str) and len(password) < 8:
            errors["password"] = "must be at least 8 characters"
        if errors:
            raise ApiError(400, "validation_error", "Request validation failed", errors)
        username = username.strip()
        if username in app.users:
            raise ApiError(409, "username_exists", "Username is already registered")
        app.users[username] = {"username": username, "password_hash": generate_password_hash(password)}
        audit("user.registered", username, {"username": username})
        return jsonify({"data": {"username": username}}), 201

    @app.post("/api/v1/auth/login")
    def login():
        data = json_body()
        errors = validate_fields(data, required={"username", "password"}, allowed={"username", "password"})
        if errors:
            raise ApiError(400, "validation_error", "Request validation failed", errors)
        user = app.users.get(data["username"])
        if not user or not check_password_hash(user["password_hash"], data["password"]):
            audit("user.login_failed", data.get("username"), {})
            raise ApiError(401, "invalid_credentials", "Invalid username or password")
        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {"sub": user["username"], "iat": now, "exp": now + timedelta(seconds=app.config["JWT_TTL_SECONDS"])},
            app.config["JWT_SECRET"],
            algorithm="HS256",
        )
        audit("user.logged_in", user["username"], {})
        return jsonify({"data": {"access_token": token, "token_type": "Bearer", "expires_in": app.config["JWT_TTL_SECONDS"]}})

    @app.get("/api/v1/items")
    @authenticated
    def list_items():
        page = positive_int_arg("page", 1)
        per_page = positive_int_arg("per_page", 20)
        if per_page > app.config["MAX_PAGE_SIZE"]:
            raise ApiError(400, "validation_error", "Request validation failed", {"per_page": f"must not exceed {app.config['MAX_PAGE_SIZE']}"})
        records = sorted(app.items.values(), key=lambda item: item["id"])
        total = len(records)
        start = (page - 1) * per_page
        return jsonify({
            "data": records[start : start + per_page],
            "pagination": {"page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page},
        })

    @app.post("/api/v1/items")
    @authenticated
    def create_item():
        data = json_body()
        errors = validate_fields(data, required={"name"}, allowed={"name", "description"})
        if isinstance(data.get("name"), str) and not 1 <= len(data["name"].strip()) <= 100:
            errors["name"] = "must be between 1 and 100 characters"
        if "description" in data and not isinstance(data["description"], str):
            errors["description"] = "must be a string"
        if errors:
            raise ApiError(400, "validation_error", "Request validation failed", errors)
        item_id = next(app.item_ids)
        item = {"id": item_id, "name": data["name"].strip(), "description": data.get("description", ""), "owner": g.user}
        app.items[item_id] = item
        audit("item.created", g.user, {"item_id": item_id})
        return jsonify({"data": item}), 201

    @app.get("/api/v1/items/<int:item_id>")
    @authenticated
    def get_item(item_id):
        return jsonify({"data": find_item(item_id)})

    @app.patch("/api/v1/items/<int:item_id>")
    @authenticated
    def update_item(item_id):
        item = find_item(item_id)
        require_owner(item)
        data = json_body()
        errors = validate_fields(data, required=set(), allowed={"name", "description"})
        if not data:
            errors["body"] = "must contain at least one field"
        if "name" in data and (not isinstance(data["name"], str) or not 1 <= len(data["name"].strip()) <= 100):
            errors["name"] = "must be a string between 1 and 100 characters"
        if "description" in data and not isinstance(data["description"], str):
            errors["description"] = "must be a string"
        if errors:
            raise ApiError(400, "validation_error", "Request validation failed", errors)
        if "name" in data:
            item["name"] = data["name"].strip()
        if "description" in data:
            item["description"] = data["description"]
        audit("item.updated", g.user, {"item_id": item_id})
        return jsonify({"data": item})

    @app.delete("/api/v1/items/<int:item_id>")
    @authenticated
    def delete_item(item_id):
        item = find_item(item_id)
        require_owner(item)
        del app.items[item_id]
        audit("item.deleted", g.user, {"item_id": item_id})
        return "", 204

    def find_item(item_id):
        item = app.items.get(item_id)
        if not item:
            raise ApiError(404, "item_not_found", "Item not found")
        return item

    def require_owner(item):
        if item["owner"] != g.user:
            raise ApiError(403, "forbidden", "You do not own this item")

    def audit(action, actor, details):
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "actor": actor,
            "ip": request.remote_addr,
            "details": details,
        }
        app.audit_events.append(event)
        app.logger.info("audit", extra={"audit_event": event})

    return app


def error_response(status, code, message, details=None):
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    response = jsonify({"error": error})
    response.status_code = status
    return response


def json_body():
    if not request.is_json:
        raise ApiError(415, "unsupported_media_type", "Content-Type must be application/json")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "invalid_json", "Request body must be a JSON object")
    return data


def validate_fields(data, required, allowed):
    errors = {}
    for field in required:
        if field not in data or not isinstance(data[field], str) or not data[field].strip():
            errors[field] = "is required and must be a non-empty string"
    unknown = sorted(set(data) - allowed)
    if unknown:
        errors["unknown_fields"] = unknown
    return errors


def positive_int_arg(name, default):
    raw = request.args.get(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        raise ApiError(400, "validation_error", "Request validation failed", {name: "must be a positive integer"})
    return value


def authenticated(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise ApiError(401, "authentication_required", "A Bearer token is required")
        try:
            payload = jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise ApiError(401, "token_expired", "The access token has expired")
        except jwt.InvalidTokenError:
            raise ApiError(401, "invalid_token", "The access token is invalid")
        username = payload.get("sub")
        if not username or username not in current_app.users:
            raise ApiError(401, "invalid_token", "The access token is invalid")
        g.user = username
        return view(*args, **kwargs)

    return wrapped


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run()
