import hmac
import json
import logging
import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import wraps
from uuid import uuid4

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, status, code, message, details=None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details


class RateLimiter:
    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, key):
        now = time.monotonic()
        with self.lock:
            timestamps = self.requests[key]
            while timestamps and timestamps[0] <= now - self.window_seconds:
                timestamps.popleft()
            if len(timestamps) >= self.limit:
                return False, 0, max(1, int(self.window_seconds - (now - timestamps[0])))
            timestamps.append(now)
            return True, self.limit - len(timestamps), self.window_seconds


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        JWT_SECRET=os.environ.get("JWT_SECRET", "change-this-in-production"),
        JWT_TTL_SECONDS=int(os.environ.get("JWT_TTL_SECONDS", "3600")),
        API_USERNAME=os.environ.get("API_USERNAME", "admin"),
        API_PASSWORD=os.environ.get("API_PASSWORD", "change-me"),
        RATE_LIMIT=int(os.environ.get("RATE_LIMIT", "100")),
        RATE_WINDOW_SECONDS=int(os.environ.get("RATE_WINDOW_SECONDS", "60")),
    )
    if config:
        app.config.update(config)

    items = {}
    audit_events = []
    limiter = RateLimiter(app.config["RATE_LIMIT"], app.config["RATE_WINDOW_SECONDS"])
    audit_logger = logging.getLogger("api.audit")
    app.extensions["items"] = items
    app.extensions["audit_events"] = audit_events

    def error_response(status, code, message, details=None):
        body = {"error": {"code": code, "message": message}}
        if details is not None:
            body["error"]["details"] = details
        return jsonify(body), status

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return error_response(error.status, error.code, error.message, error.details)

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return error_response(error.code or 500, error.name.lower().replace(" ", "_"), error.description)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled API error", exc_info=error)
        return error_response(500, "internal_error", "An unexpected error occurred")

    @app.before_request
    def apply_rate_limit():
        if not request.path.startswith("/api/"):
            return None
        key = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
        allowed, remaining, retry_after = limiter.check(key)
        g.rate_limit_remaining = remaining
        if not allowed:
            response, status = error_response(429, "rate_limit_exceeded", "Too many requests")
            response.status_code = status
            response.headers["Retry-After"] = str(retry_after)
            return response
        return None

    @app.after_request
    def add_headers_and_audit(response):
        if request.path.startswith("/api/"):
            response.headers["X-RateLimit-Limit"] = str(app.config["RATE_LIMIT"])
            response.headers["X-RateLimit-Remaining"] = str(getattr(g, "rate_limit_remaining", 0))
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": request.headers.get("X-Request-ID", str(uuid4())),
                "actor": getattr(g, "identity", None),
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "remote_addr": request.remote_addr,
            }
            audit_events.append(event)
            audit_logger.info(json.dumps(event, separators=(",", ":")))
        return response

    def require_auth(handler):
        @wraps(handler)
        def wrapped(*args, **kwargs):
            authorization = request.headers.get("Authorization", "")
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() != "bearer" or not token:
                raise ApiError(401, "authentication_required", "A Bearer token is required")
            try:
                claims = jwt.decode(token, app.config["JWT_SECRET"], algorithms=["HS256"])
            except jwt.ExpiredSignatureError as error:
                raise ApiError(401, "token_expired", "The token has expired") from error
            except jwt.InvalidTokenError as error:
                raise ApiError(401, "invalid_token", "The token is invalid") from error
            g.identity = claims.get("sub")
            if not g.identity:
                raise ApiError(401, "invalid_token", "The token is invalid")
            return handler(*args, **kwargs)

        return wrapped

    def json_object():
        if not request.is_json:
            raise ApiError(415, "unsupported_media_type", "Content-Type must be application/json")
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ApiError(400, "invalid_json", "The request body must be a JSON object")
        return data

    def validate_item(data, partial=False):
        allowed = {"name", "description"}
        errors = {}
        unknown = sorted(set(data) - allowed)
        if unknown:
            errors["fields"] = f"Unknown fields: {', '.join(unknown)}"
        if not partial or "name" in data:
            name = data.get("name")
            if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
                errors["name"] = "Must be a non-empty string of at most 100 characters"
        if "description" in data and (
            not isinstance(data["description"], str) or len(data["description"]) > 1000
        ):
            errors["description"] = "Must be a string of at most 1000 characters"
        if partial and not data:
            errors["body"] = "At least one field is required"
        if errors:
            raise ApiError(422, "validation_error", "Request validation failed", errors)
        return {
            key: value.strip() if isinstance(value, str) else value
            for key, value in data.items()
        }

    @app.post("/api/v1/auth/token")
    def issue_token():
        credentials = json_object()
        username = credentials.get("username")
        password = credentials.get("password")
        valid = (
            isinstance(username, str)
            and isinstance(password, str)
            and hmac.compare_digest(username, app.config["API_USERNAME"])
            and hmac.compare_digest(password, app.config["API_PASSWORD"])
        )
        if not valid:
            raise ApiError(401, "invalid_credentials", "Invalid username or password")
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=app.config["JWT_TTL_SECONDS"])
        token = jwt.encode(
            {"sub": username, "iat": now, "exp": expires_at},
            app.config["JWT_SECRET"],
            algorithm="HS256",
        )
        g.identity = username
        return jsonify({"access_token": token, "token_type": "Bearer", "expires_in": app.config["JWT_TTL_SECONDS"]})

    @app.get("/api/v1/items")
    @require_auth
    def list_items():
        try:
            page = int(request.args.get("page", "1"))
            per_page = int(request.args.get("per_page", "20"))
        except ValueError as error:
            raise ApiError(422, "validation_error", "Pagination values must be integers") from error
        if page < 1 or per_page < 1 or per_page > 100:
            raise ApiError(422, "validation_error", "page must be positive and per_page must be between 1 and 100")
        values = list(items.values())
        start = (page - 1) * per_page
        return jsonify(
            {
                "data": values[start : start + per_page],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": len(values),
                    "pages": (len(values) + per_page - 1) // per_page,
                },
            }
        )

    @app.post("/api/v1/items")
    @require_auth
    def create_item():
        data = validate_item(json_object())
        now = datetime.now(timezone.utc).isoformat()
        item = {"id": str(uuid4()), "description": "", "created_at": now, "updated_at": now, **data}
        items[item["id"]] = item
        return jsonify(item), 201

    def get_item_or_404(item_id):
        item = items.get(item_id)
        if item is None:
            raise ApiError(404, "not_found", "Item not found")
        return item

    @app.get("/api/v1/items/<item_id>")
    @require_auth
    def get_item(item_id):
        return jsonify(get_item_or_404(item_id))

    @app.patch("/api/v1/items/<item_id>")
    @require_auth
    def update_item(item_id):
        item = get_item_or_404(item_id)
        item.update(validate_item(json_object(), partial=True))
        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        return jsonify(item)

    @app.delete("/api/v1/items/<item_id>")
    @require_auth
    def delete_item(item_id):
        get_item_or_404(item_id)
        del items[item_id]
        return "", 204

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


app = create_app()

if __name__ == "__main__":
    app.run()
