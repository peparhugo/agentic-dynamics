from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any

import jwt
from flask import Flask, Blueprint, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException


USERS = {
    "admin": {"password": "password", "roles": ["admin"]},
}

ITEMS: list[dict[str, Any]] = [
    {"id": 1, "name": "Notebook", "description": "Hardcover notebook"},
    {"id": 2, "name": "Pen", "description": "Black gel pen"},
    {"id": 3, "name": "Mug", "description": "Ceramic coffee mug"},
]

AUDIT_LOG: list[dict[str, Any]] = []


class ApiError(Exception):
    def __init__(self, message: str, status_code: int = 400, details: dict[str, Any] | None = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def create_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY="dev-secret-change-me",
        JWT_ALGORITHM="HS256",
        JWT_EXPIRATION_MINUTES=30,
        RATE_LIMIT_REQUESTS=100,
        RATE_LIMIT_WINDOW_SECONDS=60,
    )
    if config:
        app.config.update(config)

    app.rate_limits = defaultdict(deque)  # type: ignore[attr-defined]
    app.register_blueprint(api_v1, url_prefix="/api/v1")
    register_error_handlers(app)
    register_audit_logging(app)
    return app


api_v1 = Blueprint("api_v1", __name__)


def error_response(message: str, status_code: int, details: dict[str, Any] | None = None):
    payload: dict[str, Any] = {"error": {"message": message, "status": status_code}}
    if details:
        payload["error"]["details"] = details
    return jsonify(payload), status_code


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        return error_response(error.message, error.status_code, error.details)

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        return error_response(error.description, error.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        current_app.logger.exception("Unhandled API error")
        return error_response("Internal server error", 500)


def register_audit_logging(app: Flask) -> None:
    @app.before_request
    def before_request() -> None:
        g.request_started_at = datetime.now(timezone.utc)

    @app.after_request
    def after_request(response):
        if request.path.startswith("/api/"):
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "actor": getattr(g, "current_user", None),
                "remote_addr": request.remote_addr,
            }
            AUDIT_LOG.append(event)
            current_app.logger.info("audit", extra={"audit": event})
        return response


def rate_limit(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        now = datetime.now(timezone.utc).timestamp()
        window = current_app.config["RATE_LIMIT_WINDOW_SECONDS"]
        limit = current_app.config["RATE_LIMIT_REQUESTS"]
        actor = getattr(g, "current_user", None) or request.remote_addr or "anonymous"
        key = (actor, request.endpoint)
        requests = current_app.rate_limits[key]  # type: ignore[attr-defined]

        while requests and now - requests[0] >= window:
            requests.popleft()

        remaining = max(limit - len(requests), 0)
        if len(requests) >= limit:
            response, status = error_response("Rate limit exceeded", 429)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = "0"
            return response, status

        requests.append(now)
        response = current_app.make_response(fn(*args, **kwargs))
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(remaining - 1, 0))
        return response

    return wrapper


def create_token(username: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=current_app.config["JWT_EXPIRATION_MINUTES"])
    payload = {"sub": username, "exp": expires_at, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=current_app.config["JWT_ALGORITHM"])


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise ApiError("Missing bearer token", 401)

        try:
            payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=[current_app.config["JWT_ALGORITHM"]])
        except jwt.ExpiredSignatureError as exc:
            raise ApiError("Token has expired", 401) from exc
        except jwt.InvalidTokenError as exc:
            raise ApiError("Invalid token", 401) from exc

        username = payload.get("sub")
        if username not in USERS:
            raise ApiError("Invalid token subject", 401)
        g.current_user = username
        return fn(*args, **kwargs)

    return wrapper


def require_json(required_fields: dict[str, type]) -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object", 400)

    errors: dict[str, str] = {}
    for field, expected_type in required_fields.items():
        if field not in payload:
            errors[field] = "is required"
        elif not isinstance(payload[field], expected_type):
            errors[field] = f"must be {expected_type.__name__}"
        elif expected_type is str and not payload[field].strip():
            errors[field] = "must not be blank"

    if errors:
        raise ApiError("Validation failed", 422, errors)
    return payload


def parse_pagination() -> tuple[int, int]:
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError as exc:
        raise ApiError("Pagination parameters must be integers", 400) from exc

    if page < 1:
        raise ApiError("page must be greater than or equal to 1", 400)
    if per_page < 1 or per_page > 100:
        raise ApiError("per_page must be between 1 and 100", 400)
    return page, per_page


@api_v1.get("/health")
def health():
    return jsonify({"status": "ok", "version": "v1"})


@api_v1.post("/auth/login")
@rate_limit
def login():
    payload = require_json({"username": str, "password": str})
    user = USERS.get(payload["username"])
    if not user or user["password"] != payload["password"]:
        raise ApiError("Invalid credentials", 401)
    return jsonify({"access_token": create_token(payload["username"]), "token_type": "Bearer"})


@api_v1.get("/items")
@require_auth
@rate_limit
def list_items():
    page, per_page = parse_pagination()
    total = len(ITEMS)
    start = (page - 1) * per_page
    end = start + per_page
    return jsonify(
        {
            "data": ITEMS[start:end],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page,
            },
        }
    )


@api_v1.post("/items")
@require_auth
@rate_limit
def create_item():
    payload = require_json({"name": str, "description": str})
    item = {"id": max((item["id"] for item in ITEMS), default=0) + 1, "name": payload["name"].strip(), "description": payload["description"].strip()}
    ITEMS.append(item)
    return jsonify({"data": item}), 201
