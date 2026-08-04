from flask import Blueprint, request, jsonify, g

from app.database import get_db
from app.auth import hash_password, check_password, create_token, login_required
from app.utils import validate_required_fields, validate_non_empty_string

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    ok, msg = validate_required_fields(data, ["username", "email", "password"])
    if not ok:
        return jsonify({"error": msg}), 400

    username = data["username"].strip()
    email = data["email"].strip().lower()
    password = data["password"]

    ok, msg = validate_non_empty_string(username, "username")
    if not ok:
        return jsonify({"error": msg}), 400
    if len(username) < 3:
        return jsonify({"error": "username must be at least 3 characters"}), 400

    ok, msg = validate_non_empty_string(email, "email")
    if not ok:
        return jsonify({"error": msg}), 400
    if "@" not in email:
        return jsonify({"error": "Invalid email address"}), 400

    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400

    db = get_db()
    existing = db.execute(
        "SELECT id FROM users WHERE username = ? OR email = ?", (username, email)
    ).fetchone()
    if existing:
        return jsonify({"error": "Username or email already exists"}), 409

    password_hash = hash_password(password)
    cursor = db.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        (username, email, password_hash),
    )
    db.commit()
    user_id = cursor.lastrowid
    token = create_token(user_id)

    return (
        jsonify(
            {
                "user": {"id": user_id, "username": username, "email": email},
                "token": token,
            }
        ),
        201,
    )


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    ok, msg = validate_required_fields(data, ["username", "password"])
    if not ok:
        return jsonify({"error": msg}), 400

    username = data["username"].strip()
    password = data["password"]

    db = get_db()
    user = db.execute(
        "SELECT id, username, email, password_hash FROM users WHERE username = ? OR email = ?",
        (username, username),
    ).fetchone()

    if not user or not check_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid username or password"}), 401

    token = create_token(user["id"])
    return jsonify(
        {
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
            },
            "token": token,
        }
    )


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    db = get_db()
    user = db.execute(
        "SELECT id, username, email, created_at FROM users WHERE id = ?",
        (g.current_user_id,),
    ).fetchone()
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify(
        {
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "created_at": user["created_at"],
            }
        }
    )
