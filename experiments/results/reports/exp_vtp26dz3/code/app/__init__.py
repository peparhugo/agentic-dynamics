from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from functools import wraps
from typing import Any

from flask import Flask, current_app, g, jsonify, request
from werkzeug.exceptions import BadRequest, HTTPException


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(subject: str, secret: str, lifetime: int = 3600) -> str:
    now = int(time.time())
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64encode(
        json.dumps({"sub": subject, "iat": now, "exp": now + lifetime}, separators=(",", ":")).encode()
    )
    content = f"{header}.{payload}"
    signature = hmac.new(secret.encode(), content.encode(), hashlib.sha256).digest()
    return f"{content}.{_b64encode(signature)}"


def decode_token(token: str, secret: str) -> dict[str, Any]:
    try:
        header, payload, supplied_signature = token.split(".")
        content = f"{header}.{payload}"
        signature = hmac.new(secret.encode(), content.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(signature, _b64decode(supplied_signature)):
            raise ValueError("invalid signature")
        decoded_header = json.loads(_b64decode(header))
        claims = json.loads(_b64decode(payload))
        if decoded_header.get("alg") != "HS256" or not isinstance(claims.get("sub"), str):
            raise ValueError("invalid claims")
        if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] <= time.time():
            raise ValueError("token expired")
        return claims
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("invalid or expired token") from exc


class RateLimiter:
    def __init__(self, limit: int, window: int):
        self.limit = limit
        self.window = window
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> int | None:
        now = time.time()
        with self._lock:
            timestamps = self._requests[key]
            while timestamps and timestamps[0] <= now - self.window:
                timestamps.popleft()
            if len(timestamps) >= self.limit:
                return max(1, int(timestamps[0] + self.window - now) + 1)
            timestamps.append(now)
        return None


def _error(status: int, code: str, message: str, details: dict[str, str] | None = None):
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return jsonify(body), status


def _authenticate():
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return _error(401, "unauthorized", "A Bearer token is required")
    try:
        g.user = decode_token(token, current_app.config["JWT_SECRET"])["sub"]
    except ValueError:
        return _error(401, "unauthorized", "The token is invalid or expired")
    return None


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        error = _authenticate()
        return error if error else view(*args, **kwargs)

    return wrapped


def _validated_item() -> tuple[dict[str, Any] | None, Any | None]:
    if not request.is_json:
        return None, _error(415, "unsupported_media_type", "Content-Type must be application/json")
    data = request.get_json()
    if not isinstance(data, dict):
        return None, _error(400, "validation_error", "Request body must be an object")
    errors: dict[str, str] = {}
    name = data.get("name")
    price = data.get("price")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        errors["name"] = "must be a non-empty string of at most 120 characters"
    if isinstance(price, bool) or not isinstance(price, (int, float)) or price < 0:
        errors["price"] = "must be a non-negative number"
    unknown = set(data) - {"name", "price"}
    if unknown:
        errors["body"] = f"unknown fields: {', '.join(sorted(unknown))}"
    if errors:
        return None, _error(400, "validation_error", "Request validation failed", errors)
    return {"name": name.strip(), "price": price}, None


def create_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        JWT_SECRET="change-this-secret-in-production",
        JWT_LIFETIME_SECONDS=3600,
        RATE_LIMIT=100,
        RATE_LIMIT_WINDOW_SECONDS=60,
        USERS={"admin": "change-me"},
    )
    if config:
        app.config.update(config)

    app.extensions["rate_limiter"] = RateLimiter(
        app.config["RATE_LIMIT"], app.config["RATE_LIMIT_WINDOW_SECONDS"]
    )
    app.extensions["items"] = {}
    app.extensions["audit_log"] = []

    @app.before_request
    def apply_rate_limit():
        key = request.remote_addr or "unknown"
        retry_after = app.extensions["rate_limiter"].check(key)
        if retry_after is not None:
            response, status = _error(429, "rate_limit_exceeded", "Too many requests")
            response.headers["Retry-After"] = str(retry_after)
            return response, status
        return None

    @app.after_request
    def audit_request(response):
        event = {
            "timestamp": int(time.time()),
            "request_id": request.headers.get("X-Request-ID", str(uuid.uuid4())),
            "actor": getattr(g, "user", None),
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "remote_addr": request.remote_addr,
        }
        app.extensions["audit_log"].append(event)
        app.logger.info("audit %s", json.dumps(event, separators=(",", ":")))
        response.headers["X-Request-ID"] = event["request_id"]
        return response

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        code = "bad_request" if isinstance(exc, BadRequest) else exc.name.lower().replace(" ", "_")
        return _error(exc.code or 500, code, exc.description)

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        app.logger.exception("Unhandled request error", exc_info=exc)
        return _error(500, "internal_server_error", "An unexpected error occurred")

    @app.post("/api/v1/auth/token")
    def issue_token():
        if not request.is_json:
            return _error(415, "unsupported_media_type", "Content-Type must be application/json")
        data = request.get_json()
        if not isinstance(data, dict):
            return _error(400, "validation_error", "Request body must be an object")
        username, password = data.get("username"), data.get("password")
        expected = app.config["USERS"].get(username) if isinstance(username, str) else None
        if expected is None or not isinstance(password, str) or not hmac.compare_digest(expected, password):
            return _error(401, "invalid_credentials", "Invalid username or password")
        token = create_token(username, app.config["JWT_SECRET"], app.config["JWT_LIFETIME_SECONDS"])
        return jsonify({"access_token": token, "token_type": "Bearer", "expires_in": app.config["JWT_LIFETIME_SECONDS"]})

    @app.get("/api/v1/items")
    @require_auth
    def list_items():
        try:
            page = int(request.args.get("page", 1))
            per_page = int(request.args.get("per_page", 20))
        except ValueError:
            return _error(400, "validation_error", "Pagination parameters must be integers")
        if page < 1 or per_page < 1 or per_page > 100:
            return _error(400, "validation_error", "page must be positive and per_page must be between 1 and 100")
        records = list(app.extensions["items"].values())
        start = (page - 1) * per_page
        return jsonify(
            {
                "data": records[start : start + per_page],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": len(records),
                    "pages": (len(records) + per_page - 1) // per_page,
                },
            }
        )

    @app.post("/api/v1/items")
    @require_auth
    def create_item():
        data, error = _validated_item()
        if error:
            return error
        item_id = str(uuid.uuid4())
        item = {"id": item_id, **data}
        app.extensions["items"][item_id] = item
        return jsonify({"data": item}), 201

    @app.get("/api/v1/items/<item_id>")
    @require_auth
    def get_item(item_id: str):
        item = app.extensions["items"].get(item_id)
        return jsonify({"data": item}) if item else _error(404, "not_found", "Item not found")

    @app.put("/api/v1/items/<item_id>")
    @require_auth
    def update_item(item_id: str):
        if item_id not in app.extensions["items"]:
            return _error(404, "not_found", "Item not found")
        data, error = _validated_item()
        if error:
            return error
        item = {"id": item_id, **data}
        app.extensions["items"][item_id] = item
        return jsonify({"data": item})

    @app.delete("/api/v1/items/<item_id>")
    @require_auth
    def delete_item(item_id: str):
        if app.extensions["items"].pop(item_id, None) is None:
            return _error(404, "not_found", "Item not found")
        return "", 204

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    if not app.debug:
        app.logger.setLevel(logging.INFO)
    return app


__all__ = ["create_app", "create_token", "decode_token"]
