import base64
import hashlib
import hmac
import json
import re
import time
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db


bp = Blueprint("auth", __name__, url_prefix="/auth")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _encode_part(value):
    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _decode_part(value):
    padding = "=" * (-len(value) % 4)
    return json.loads(base64.urlsafe_b64decode(value + padding))


def create_token(user_id):
    now = int(time.time())
    header = _encode_part({"alg": "HS256", "typ": "JWT"})
    payload = _encode_part(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + current_app.config["JWT_TTL_SECONDS"],
        }
    )
    body = f"{header}.{payload}"
    signature = hmac.new(
        current_app.config["JWT_SECRET"].encode(), body.encode(), hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{body}.{encoded_signature}"


def decode_token(token):
    try:
        header, payload, signature = token.split(".")
        body = f"{header}.{payload}"
        expected = hmac.new(
            current_app.config["JWT_SECRET"].encode(), body.encode(), hashlib.sha256
        ).digest()
        supplied = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        claims = _decode_part(payload)
        if not hmac.compare_digest(expected, supplied):
            return None
        if _decode_part(header).get("alg") != "HS256" or claims.get("exp", 0) < time.time():
            return None
        return int(claims["sub"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def login_required(view):
    @wraps(view)
    def wrapped(**kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return jsonify(error="unauthorized", message="Bearer token required"), 401
        user_id = decode_token(token)
        user = (
            get_db()
            .execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,))
            .fetchone()
            if user_id is not None
            else None
        )
        if user is None:
            return jsonify(error="unauthorized", message="Invalid or expired token"), 401
        g.user = user
        return view(**kwargs)

    return wrapped


def _json_body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return None, (jsonify(error="validation_error", message="JSON object required"), 400)
    return body, None


@bp.post("/register")
def register():
    body, error = _json_body()
    if error:
        return error
    name = str(body.get("name", "")).strip()
    email = str(body.get("email", "")).strip().lower()
    password = body.get("password", "")
    if not name or len(name) > 100:
        return jsonify(error="validation_error", message="Name is required and must be at most 100 characters"), 400
    if not EMAIL_PATTERN.match(email) or len(email) > 254:
        return jsonify(error="validation_error", message="A valid email is required"), 400
    if not isinstance(password, str) or len(password) < 8:
        return jsonify(error="validation_error", message="Password must be at least 8 characters"), 400

    database = get_db()
    try:
        cursor = database.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        database.commit()
    except Exception as exc:
        if "UNIQUE constraint failed" not in str(exc):
            raise
        return jsonify(error="conflict", message="Email is already registered"), 409
    return jsonify(user={"id": cursor.lastrowid, "name": name, "email": email}), 201


@bp.post("/login")
def login():
    body, error = _json_body()
    if error:
        return error
    email = str(body.get("email", "")).strip().lower()
    password = body.get("password", "")
    user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user is None or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
        return jsonify(error="unauthorized", message="Invalid email or password"), 401
    return jsonify(
        access_token=create_token(user["id"]),
        token_type="Bearer",
        expires_in=current_app.config["JWT_TTL_SECONDS"],
        user={"id": user["id"], "name": user["name"], "email": user["email"]},
    )


@bp.get("/me")
@login_required
def me():
    return jsonify(user=dict(g.user))
