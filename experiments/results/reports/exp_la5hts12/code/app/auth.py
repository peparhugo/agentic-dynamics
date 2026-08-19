from flask import Blueprint, current_app, g, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_db

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _public_user(row):
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "is_admin": bool(row["is_admin"]),
        "created_at": row["created_at"],
    }


def _find_user_by_username(username):
    return get_db().execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()


def _find_user_by_email(email):
    return get_db().execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()


def _find_user_by_id(user_id):
    return get_db().execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()


@bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not username:
        return jsonify({"error": "username is required"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "a valid email is required"}), 400
    if len(password) < current_app.config["PASSWORD_MIN_LENGTH"]:
        return jsonify({"error": "password must be at least 6 characters"}), 400

    db = get_db()
    if _find_user_by_username(username):
        return jsonify({"error": "username already taken"}), 409
    if _find_user_by_email(email):
        return jsonify({"error": "email already registered"}), 409

    password_hash = generate_password_hash(password)
    cursor = db.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        (username, email, password_hash),
    )
    db.commit()

    user = _find_user_by_id(cursor.lastrowid)
    return jsonify(_public_user(user)), 201


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = _find_user_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    identity = str(user["id"])
    return jsonify(
        {
            "access_token": create_access_token(identity=identity),
            "refresh_token": create_refresh_token(identity=identity),
            "user": _public_user(user),
        }
    ), 200


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    return jsonify({"access_token": create_access_token(identity=identity)}), 200


@bp.get("/me")
@jwt_required()
def me():
    identity = get_jwt_identity()
    user = _find_user_by_id(identity)
    if user is None:
        return jsonify({"error": "user not found"}), 404
    return jsonify(_public_user(user)), 200


def current_user():
    from flask_jwt_extended import get_jwt_identity

    identity = get_jwt_identity()
    if identity is None:
        return None
    return _find_user_by_id(identity)


def get_current_user():
    return getattr(g, "_current_user", None)
