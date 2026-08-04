"""User registration, login, and JWT authentication."""
import datetime
import re
from functools import wraps

import jwt
from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .errors import APIError

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LEN = 8


# --------------------------------------------------------------------------- helpers

def create_token(user_id: int) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + datetime.timedelta(seconds=current_app.config["JWT_EXPIRES_SECONDS"]),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"],
                      algorithm=current_app.config["JWT_ALGORITHM"])


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, current_app.config["SECRET_KEY"],
                          algorithms=[current_app.config["JWT_ALGORITHM"]])
    except jwt.ExpiredSignatureError:
        raise APIError("Token has expired", 401)
    except jwt.InvalidTokenError:
        raise APIError("Invalid token", 401)


def user_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "created_at": row["created_at"],
    }


def require_auth(view):
    """Decorator: require a valid `Authorization: Bearer <token>` header."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise APIError("Missing or malformed Authorization header", 401)
        payload = decode_token(header.removeprefix("Bearer ").strip())
        user = get_db().execute(
            "SELECT * FROM users WHERE id = ?", (int(payload["sub"]),)
        ).fetchone()
        if user is None:
            raise APIError("User no longer exists", 401)
        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


def _json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise APIError("Request body must be a JSON object", 400)
    return data


# --------------------------------------------------------------------------- routes

@bp.post("/register")
def register():
    data = _json_body()
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip()
    password = data.get("password", "")

    errors = {}
    if not USERNAME_RE.match(username):
        errors["username"] = "Must be 3-32 chars: letters, digits, '_', '.', '-'"
    if not EMAIL_RE.match(email):
        errors["email"] = "Must be a valid email address"
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LEN:
        errors["password"] = f"Must be at least {MIN_PASSWORD_LEN} characters"
    if errors:
        raise APIError("Validation failed", 400, {"details": errors})

    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        raise APIError("Username already taken", 409)
    if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        raise APIError("Email already registered", 409)

    cur = db.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        (username, email, generate_password_hash(password)),
    )
    db.commit()
    user = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify({"user": user_to_dict(user), "token": create_token(user["id"])}), 201


@bp.post("/login")
def login():
    data = _json_body()
    identifier = str(data.get("username") or data.get("email") or "").strip()
    password = data.get("password", "")
    if not identifier or not password:
        raise APIError("username (or email) and password are required", 400)

    user = get_db().execute(
        "SELECT * FROM users WHERE username = ? OR email = ?", (identifier, identifier)
    ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        raise APIError("Invalid credentials", 401)

    return jsonify({"user": user_to_dict(user), "token": create_token(user["id"])})


@bp.get("/me")
@require_auth
def me():
    return jsonify({"user": user_to_dict(g.current_user)})
