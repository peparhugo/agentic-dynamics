from datetime import datetime, timedelta, timezone

import jwt
from flask import Blueprint, current_app, g, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

from .common import auth_required, error, json_body
from .db import get_db


auth_bp = Blueprint("auth", __name__)


def serialize_user(user):
    return {"id": user["id"], "username": user["username"], "email": user["email"]}


@auth_bp.post("/register")
def register():
    data, response = json_body()
    if response:
        return response
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip():
        return error("username is required")
    if not isinstance(email, str) or "@" not in email:
        return error("a valid email is required")
    if not isinstance(password, str) or len(password) < 8:
        return error("password must be at least 8 characters")
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO users(username, email, password_hash) VALUES (?, ?, ?)",
            (username.strip(), email.strip().lower(), generate_password_hash(password)),
        )
        db.commit()
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            return error("username or email already exists", 409)
        raise
    user = db.execute(
        "SELECT id, username, email FROM users WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return jsonify(serialize_user(user)), 201


@auth_bp.post("/login")
def login():
    data, response = json_body()
    if response:
        return response
    email = data.get("email")
    password = data.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return error("email and password are required")
    user = get_db().execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return error("invalid credentials", 401)
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(user["id"]),
            "iat": now,
            "exp": now + timedelta(seconds=current_app.config["JWT_TTL_SECONDS"]),
        },
        current_app.config["JWT_SECRET"],
        algorithm="HS256",
    )
    return jsonify(token=token, user=serialize_user(user))


@auth_bp.get("/me")
@auth_required
def me():
    return jsonify(serialize_user(g.user))


@auth_bp.get("/users")
@auth_required
def users():
    rows = get_db().execute("SELECT id, username, email FROM users ORDER BY username").fetchall()
    return jsonify(items=[serialize_user(row) for row in rows])
