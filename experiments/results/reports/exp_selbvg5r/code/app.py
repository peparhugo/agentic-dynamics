from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from functools import wraps
from typing import Any

from flask import Flask, Blueprint, current_app, g, jsonify, request


USERS = {
    "admin": {
        "password": "password",
        "roles": ["admin"],
    }
}

ITEMS = [
    {"id": 1, "name": "Notebook", "quantity": 12},
    {"id": 2, "name": "Pencil", "quantity": 100},
    {"id": 3, "name": "Backpack", "quantity": 7},
]


class APIError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "bad_request"):
        self.message = message
        self.status_code = status_code
        self.code = code


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(value: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), value.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def create_token(username: str) -> str:
    now = int(time.time())
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + int(current_app.config["JWT_TTL_SECONDS"]),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join(
        [
            _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    return f"{signing_input}.{_sign(signing_input, current_app.config['JWT_SECRET'])}"


def verify_token(token: str) -> dict[str, Any]:
    try:
        header, payload, signature = token.split(".")
    except ValueError as exc:
        raise APIError("Invalid bearer token", 401, "invalid_token") from exc

    signing_input = f"{header}.{payload}"
    expected = _sign(signing_input, current_app.config["JWT_SECRET"])
    if not hmac.compare_digest(signature, expected):
        raise APIError("Invalid bearer token", 401, "invalid_token")

    try:
        claims = json.loads(_b64decode(payload))
    except (json.JSONDecodeError, ValueError) as exc:
        raise APIError("Invalid bearer token", 401, "invalid_token") from exc

    if int(claims.get("exp", 0)) < int(time.time()):
        raise APIError("Bearer token has expired", 401, "token_expired")
    if claims.get("sub") not in USERS:
        raise APIError("Unknown token subject", 401, "invalid_token")
    return claims


def require_auth(handler):
    @wraps(handler)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise APIError("Missing bearer token", 401, "authentication_required")
        claims = verify_token(token)
        g.current_user = claims["sub"]
        return handler(*args, **kwargs)

    return wrapper


def require_json() -> dict[str, Any]:
    if not request.is_json:
        raise APIError("Request body must be JSON", 400, "invalid_json")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise APIError("JSON body must be an object", 400, "invalid_json")
    return data


def parse_pagination() -> tuple[int, int]:
    try:
        page = int(request.args.get("page", "1"))
        per_page = int(request.args.get("per_page", "20"))
    except ValueError as exc:
        raise APIError("page and per_page must be integers", 400, "invalid_pagination") from exc
    if page < 1:
        raise APIError("page must be greater than or equal to 1", 400, "invalid_pagination")
    if per_page < 1 or per_page > current_app.config["MAX_PER_PAGE"]:
        raise APIError(
            f"per_page must be between 1 and {current_app.config['MAX_PER_PAGE']}",
            400,
            "invalid_pagination",
        )
    return page, per_page


def paginate(records: list[dict[str, Any]], page: int, per_page: int) -> dict[str, Any]:
    total = len(records)
    start = (page - 1) * per_page
    return {
        "data": records[start : start + per_page],
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
        },
    }


def create_api_blueprint() -> Blueprint:
    api = Blueprint("api_v1", __name__, url_prefix="/api/v1")

    @api.post("/auth/login")
    def login():
        data = require_json()
        username = data.get("username")
        password = data.get("password")
        if not isinstance(username, str) or not username.strip():
            raise APIError("username is required", 400, "validation_error")
        if not isinstance(password, str) or not password:
            raise APIError("password is required", 400, "validation_error")
        user = USERS.get(username)
        if not user or not hmac.compare_digest(password, user["password"]):
            raise APIError("Invalid username or password", 401, "invalid_credentials")
        g.current_user = username
        return jsonify({"access_token": create_token(username), "token_type": "Bearer"})

    @api.get("/items")
    @require_auth
    def list_items():
        page, per_page = parse_pagination()
        return jsonify(paginate(list(current_app.config["ITEM_STORE"]), page, per_page))

    @api.post("/items")
    @require_auth
    def create_item():
        data = require_json()
        name = data.get("name")
        quantity = data.get("quantity")
        if not isinstance(name, str) or not name.strip():
            raise APIError("name is required", 400, "validation_error")
        if not isinstance(quantity, int) or quantity < 0:
            raise APIError("quantity must be a non-negative integer", 400, "validation_error")

        store = current_app.config["ITEM_STORE"]
        item = {"id": max([record["id"] for record in store], default=0) + 1, "name": name.strip(), "quantity": quantity}
        store.append(item)
        return jsonify({"data": item}), 201

    @api.get("/audit-logs")
    @require_auth
    def list_audit_logs():
        page, per_page = parse_pagination()
        return jsonify(paginate(list(current_app.config["AUDIT_LOG"]), page, per_page))

    return api


def create_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        JWT_SECRET="change-me-in-production",
        JWT_TTL_SECONDS=3600,
        RATE_LIMIT_REQUESTS=100,
        RATE_LIMIT_WINDOW_SECONDS=60,
        MAX_PER_PAGE=50,
        ITEM_STORE=[item.copy() for item in ITEMS],
        AUDIT_LOG=[],
        RATE_LIMIT_STORE={},
    )
    if config:
        app.config.update(config)

    @app.before_request
    def rate_limit():
        if not request.path.startswith("/api/"):
            return None
        now = time.time()
        window = int(app.config["RATE_LIMIT_WINDOW_SECONDS"])
        limit = int(app.config["RATE_LIMIT_REQUESTS"])
        key = (request.remote_addr or "unknown", request.path)
        bucket = [timestamp for timestamp in app.config["RATE_LIMIT_STORE"].get(key, []) if timestamp > now - window]
        if len(bucket) >= limit:
            raise APIError("Rate limit exceeded", 429, "rate_limit_exceeded")
        bucket.append(now)
        app.config["RATE_LIMIT_STORE"][key] = bucket
        return None

    @app.after_request
    def audit(response):
        if request.path.startswith("/api/"):
            app.config["AUDIT_LOG"].append(
                {
                    "method": request.method,
                    "path": request.path,
                    "status_code": response.status_code,
                    "user": getattr(g, "current_user", None),
                    "remote_addr": request.remote_addr,
                    "timestamp": int(time.time()),
                }
            )
        return response

    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        response = jsonify({"error": {"code": error.code, "message": error.message}})
        response.status_code = error.status_code
        return response

    @app.errorhandler(404)
    def handle_not_found(_error):
        return jsonify({"error": {"code": "not_found", "message": "Resource not found"}}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(_error):
        return jsonify({"error": {"code": "method_not_allowed", "message": "Method not allowed"}}), 405

    app.register_blueprint(create_api_blueprint())
    return app


if __name__ == "__main__":
    create_app().run(debug=True)
