from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from collections import defaultdict, deque
from functools import wraps
from typing import Any

from flask import Flask, g, jsonify, request


USERS = {"admin": "password"}


class APIError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "bad_request"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(username: str, secret: str, ttl_seconds: int = 3600) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": username, "iat": int(time.time()), "exp": int(time.time()) + ttl_seconds}
    signing_input = f"{_b64encode(json.dumps(header, separators=(',', ':')).encode())}.{_b64encode(json.dumps(payload, separators=(',', ':')).encode())}"
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64encode(signature)}"


def verify_token(token: str, secret: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}"
        expected = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(signature_b64)):
            raise APIError("Invalid token", 401, "invalid_token")
        payload = json.loads(_b64decode(payload_b64))
    except (ValueError, json.JSONDecodeError, base64.binascii.Error):
        raise APIError("Invalid token", 401, "invalid_token")

    if payload.get("exp", 0) < int(time.time()):
        raise APIError("Token expired", 401, "token_expired")
    return payload


def create_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="dev-secret-change-me",
        RATE_LIMIT=60,
        RATE_LIMIT_WINDOW_SECONDS=60,
        TESTING=False,
    )
    if config:
        app.config.update(config)

    app.items: list[dict[str, Any]] = []
    app.next_item_id = 1
    app.rate_limits: dict[str, deque[float]] = defaultdict(deque)
    app.audit_events: list[dict[str, Any]] = []

    audit_logger = logging.getLogger("audit")

    def audit(action: str, status: str, **extra: Any) -> None:
        event = {
            "action": action,
            "status": status,
            "actor": getattr(g, "user", None),
            "path": request.path,
            "method": request.method,
            "timestamp": int(time.time()),
            **extra,
        }
        app.audit_events.append(event)
        audit_logger.info(json.dumps(event, sort_keys=True))

    def validate_json(required_fields: dict[str, type]) -> dict[str, Any]:
        if not request.is_json:
            raise APIError("Expected JSON request body", 415, "unsupported_media_type")
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise APIError("Invalid JSON request body", 400, "invalid_json")

        errors = {}
        for field, expected_type in required_fields.items():
            if field not in data:
                errors[field] = "required"
            elif not isinstance(data[field], expected_type) or (expected_type is str and not data[field].strip()):
                errors[field] = f"must be a non-empty {expected_type.__name__}"
        if errors:
            raise APIError("Validation failed", 422, "validation_error") from ValidationDetails(errors)
        return data

    def client_key() -> str:
        auth = request.headers.get("Authorization", "")
        return auth or request.remote_addr or "unknown"

    @app.before_request
    def rate_limit() -> None:
        if app.config["TESTING"] and app.config.get("DISABLE_RATE_LIMIT"):
            return
        now = time.time()
        window = app.config["RATE_LIMIT_WINDOW_SECONDS"]
        bucket = app.rate_limits[client_key()]
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        if len(bucket) >= app.config["RATE_LIMIT"]:
            raise APIError("Rate limit exceeded", 429, "rate_limited")
        bucket.append(now)

    def require_auth(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                raise APIError("Missing bearer token", 401, "missing_token")
            payload = verify_token(auth.removeprefix("Bearer ").strip(), app.config["SECRET_KEY"])
            g.user = payload["sub"]
            return func(*args, **kwargs)

        return wrapper

    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        validation_errors = None
        if error.__cause__ and isinstance(error.__cause__, ValidationDetails):
            validation_errors = error.__cause__.errors
        body = {"error": {"code": error.code, "message": error.message}}
        if validation_errors:
            body["error"]["fields"] = validation_errors
        audit("request_failed", "failure", error=error.code)
        return jsonify(body), error.status_code

    @app.errorhandler(404)
    def handle_not_found(_error):
        return jsonify({"error": {"code": "not_found", "message": "Resource not found"}}), 404

    @app.errorhandler(Exception)
    def handle_unexpected(error):
        app.logger.exception("Unhandled API error", exc_info=error)
        audit("request_failed", "failure", error="internal_error")
        return jsonify({"error": {"code": "internal_error", "message": "Internal server error"}}), 500

    @app.post("/api/v1/auth/login")
    def login():
        data = validate_json({"username": str, "password": str})
        if USERS.get(data["username"]) != data["password"]:
            raise APIError("Invalid credentials", 401, "invalid_credentials")
        token = create_token(data["username"], app.config["SECRET_KEY"])
        audit("login", "success", username=data["username"])
        return jsonify({"access_token": token, "token_type": "Bearer"})

    @app.get("/api/v1/items")
    @require_auth
    def list_items():
        page = parse_positive_int("page", 1)
        per_page = parse_positive_int("per_page", 10, maximum=100)
        start = (page - 1) * per_page
        end = start + per_page
        audit("list_items", "success")
        return jsonify(
            {
                "data": app.items[start:end],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": len(app.items),
                    "pages": (len(app.items) + per_page - 1) // per_page,
                },
            }
        )

    @app.post("/api/v1/items")
    @require_auth
    def create_item():
        data = validate_json({"name": str})
        item = {"id": app.next_item_id, "name": data["name"].strip()}
        app.next_item_id += 1
        app.items.append(item)
        audit("create_item", "success", item_id=item["id"])
        return jsonify({"data": item}), 201

    return app


class ValidationDetails(Exception):
    def __init__(self, errors: dict[str, str]):
        super().__init__("validation details")
        self.errors = errors


def parse_positive_int(name: str, default: int, maximum: int | None = None) -> int:
    raw = request.args.get(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise APIError(f"{name} must be an integer", 422, "validation_error")
    if value < 1 or (maximum is not None and value > maximum):
        raise APIError(f"{name} out of range", 422, "validation_error")
    return value


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
