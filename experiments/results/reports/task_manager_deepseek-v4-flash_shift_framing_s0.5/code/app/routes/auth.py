from flask import Blueprint, g, jsonify, request

from app.auth import auth_required, issue_token
from app.db import get_db, row_to_dict
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _user_dict(user):
    data = row_to_dict(user)
    data.pop("password_hash", None)
    return data


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not username or not email or not password:
        return jsonify({"error": "username, email and password are required"}), 400
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "invalid email address"}), 400
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400

    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, generate_password_hash(password)),
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 - surfaces UNIQUE constraint
        if "UNIQUE" in str(exc):
            return jsonify({"error": "username or email already taken"}), 409
        raise
    user = db.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify({"user": _user_dict(user)}), 201


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    identifier = (payload.get("identifier") or payload.get("username") or "").strip().lower()
    password = payload.get("password") or ""

    if not identifier or not password:
        return jsonify({"error": "identifier and password are required"}), 400

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username = ? OR email = ?", (identifier, identifier)
    ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    token = issue_token(user["id"])
    return jsonify({"token": token, "user": _user_dict(user)}), 200


@auth_bp.get("/me")
@auth_required
def me():
    return jsonify({"user": _user_dict(g.user)}), 200
