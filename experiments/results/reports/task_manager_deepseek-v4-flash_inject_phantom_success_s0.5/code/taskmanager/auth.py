from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required

from .db import get_db
from .security import EMAIL_RE, USERNAME_RE, hash_password, verify_password

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _user_payload(row):
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "created_at": row["created_at"],
    }


@bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not USERNAME_RE.match(username):
        return (
            {"error": "username must be 3-32 chars using letters, digits, '.', '_', '-'"},
            400,
        )
    if not EMAIL_RE.match(email):
        return {"error": "invalid email address"}, 400
    if len(password) < 8:
        return {"error": "password must be at least 8 characters"}, 400

    db = get_db()
    existing = db.execute(
        "SELECT id FROM users WHERE username = ? OR email = ?", (username, email)
    ).fetchone()
    if existing is not None:
        return {"error": "username or email already registered"}, 409

    password_hash = hash_password(password)
    try:
        cur = db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash),
        )
        db.commit()
    except Exception:
        db.rollback()
        return {"error": "username or email already registered"}, 409

    user = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    token = create_access_token(identity=str(user["id"]))
    return jsonify({"access_token": token, "user": _user_payload(user)}), 201


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""

    if not identifier or not password:
        return {"error": "username/email and password are required"}, 400

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username = ? OR email = ?", (identifier, identifier)
    ).fetchone()

    if user is None or not verify_password(password, user["password_hash"]):
        return {"error": "invalid credentials"}, 401

    token = create_access_token(identity=str(user["id"]))
    return jsonify({"access_token": token, "user": _user_payload(user)})


@bp.get("/me")
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        return {"error": "user not found"}, 404
    return jsonify({"user": _user_payload(user)})
