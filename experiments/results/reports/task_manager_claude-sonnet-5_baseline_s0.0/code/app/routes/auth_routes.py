import re

from flask import Blueprint, g, jsonify, request

from app import models
from app.auth import encode_token, token_required

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not email or not password:
        return jsonify({"error": "username, email and password are required"}), 400
    if len(username) < 3:
        return jsonify({"error": "username must be at least 3 characters"}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "invalid email address"}), 400
    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400

    if models.get_user_by_username(username):
        return jsonify({"error": "username already taken"}), 409
    if models.get_user_by_email(email):
        return jsonify({"error": "email already registered"}), 409

    try:
        user = models.create_user(username, email, password)
    except ValueError:
        return jsonify({"error": "unable to create user"}), 409

    token = encode_token(user["id"])
    return jsonify({"user": user, "token": token}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = models.get_user_by_username(username)
    if user is None:
        user = models.get_user_by_email(username.lower())
    if user is None or not models.verify_password(user, password):
        return jsonify({"error": "invalid credentials"}), 401

    token = encode_token(user["id"])
    public_user = {"id": user["id"], "username": user["username"], "email": user["email"],
                    "created_at": user["created_at"]}
    return jsonify({"user": public_user, "token": token}), 200


@auth_bp.get("/me")
@token_required
def me():
    return jsonify({"user": dict(g.current_user)}), 200
