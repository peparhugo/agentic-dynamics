import base64
import hashlib
import hmac
import json
import re
import time
from functools import wraps

from flask import current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _b64encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id):
    now = int(time.time())
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64encode(
        json.dumps(
            {"sub": str(user_id), "iat": now, "exp": now + current_app.config["JWT_EXPIRES_SECONDS"]},
            separators=(",", ":"),
        ).encode()
    )
    message = f"{header}.{payload}"
    signature = hmac.new(
        current_app.config["SECRET_KEY"].encode(), message.encode(), hashlib.sha256
    ).digest()
    return f"{message}.{_b64encode(signature)}"


def decode_token(token):
    try:
        header, payload, signature = token.split(".")
        message = f"{header}.{payload}"
        expected = hmac.new(
            current_app.config["SECRET_KEY"].encode(), message.encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(signature)):
            return None
        data = json.loads(_b64decode(payload))
        if data.get("exp", 0) < int(time.time()):
            return None
        return int(data["sub"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return jsonify(error="Authentication required"), 401
        user_id = decode_token(authorization[7:])
        user = (
            get_db()
            .execute("SELECT id, username, email, created_at FROM users WHERE id = ?", (user_id,))
            .fetchone()
            if user_id is not None
            else None
        )
        if user is None:
            return jsonify(error="Invalid or expired token"), 401
        g.user = user
        return view(*args, **kwargs)

    return wrapped


def register_routes(app):
    @app.post("/api/auth/register")
    def register():
        data = request.get_json(silent=True) or {}
        username = str(data.get("username", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        password = data.get("password", "")
        errors = {}
        if len(username) < 3 or len(username) > 50:
            errors["username"] = "Username must be between 3 and 50 characters"
        if not EMAIL_RE.fullmatch(email) or len(email) > 254:
            errors["email"] = "A valid email is required"
        if not isinstance(password, str) or len(password) < 8:
            errors["password"] = "Password must be at least 8 characters"
        if errors:
            return jsonify(error="Validation failed", details=errors), 400
        db = get_db()
        try:
            cursor = db.execute(
                "INSERT INTO users(username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, generate_password_hash(password)),
            )
            db.commit()
        except Exception as error:
            if "UNIQUE constraint failed" not in str(error):
                raise
            return jsonify(error="Username or email already exists"), 409
        user = db.execute(
            "SELECT id, username, email, created_at FROM users WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return jsonify(user=dict(user), token=create_token(user["id"])), 201

    @app.post("/api/auth/login")
    def login():
        data = request.get_json(silent=True) or {}
        identifier = str(data.get("email", data.get("username", ""))).strip()
        password = data.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE OR username = ? COLLATE NOCASE",
            (identifier, identifier),
        ).fetchone()
        if user is None or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
            return jsonify(error="Invalid credentials"), 401
        public_user = {key: user[key] for key in ("id", "username", "email", "created_at")}
        return jsonify(user=public_user, token=create_token(user["id"]))

    @app.get("/api/auth/me")
    @auth_required
    def me():
        return jsonify(user=dict(g.user))

    @app.get("/api/users")
    @auth_required
    def users():
        rows = get_db().execute(
            "SELECT id, username, email, created_at FROM users ORDER BY username COLLATE NOCASE"
        ).fetchall()
        return jsonify(users=[dict(row) for row in rows])
