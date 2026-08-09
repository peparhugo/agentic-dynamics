import re

from flask import Blueprint, request, jsonify, g

from taskapi.auth import hash_password, verify_password, create_token, login_required
from taskapi.database import query_one, execute, execute_returning

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    errors = {}
    if not username or len(username) < 3 or len(username) > 64:
        errors["username"] = "Username must be 3-64 characters"
    if not email or not EMAIL_RE.match(email):
        errors["email"] = "Valid email is required"
    if not password or len(password) < 6:
        errors["password"] = "Password must be at least 6 characters"
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    existing = query_one(
        "SELECT id FROM users WHERE username = ? OR email = ?", (username, email)
    )
    if existing:
        return jsonify({"error": "Username or email already taken"}), 409

    password_hash = hash_password(password)
    user_id = execute_returning(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        (username, email, password_hash),
    )
    token = create_token(user_id)

    return jsonify({
        "message": "Registration successful",
        "user": {"id": user_id, "username": username, "email": email},
        "token": token,
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    credential = (data.get("username") or data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not credential or not password:
        return jsonify({"error": "Username/email and password are required"}), 400

    user = query_one(
        "SELECT id, username, email, password_hash FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?",
        (credential, credential),
    )
    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid credentials"}), 401

    token = create_token(user["id"])
    return jsonify({
        "message": "Login successful",
        "user": {"id": user["id"], "username": user["username"], "email": user["email"]},
        "token": token,
    }), 200


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return jsonify({"user": g.current_user}), 200
