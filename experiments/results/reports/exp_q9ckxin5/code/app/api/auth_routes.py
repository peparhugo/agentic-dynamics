"""Authentication endpoints: register, login, current user."""
from __future__ import annotations

import re

from flask import Blueprint, g, jsonify, request

from app.auth import generate_token, token_required
from app.extensions import db
from app.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,80}$")
MIN_PASSWORD_LENGTH = 8


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    errors = {}
    if not USERNAME_RE.match(username):
        errors["username"] = (
            "Username must be 3-80 characters (letters, digits, '_', '.', '-')."
        )
    if not EMAIL_RE.match(email):
        errors["email"] = "A valid email address is required."
    if len(password) < MIN_PASSWORD_LENGTH:
        errors["password"] = (
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already taken"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = generate_token(user)
    return jsonify({"user": user.to_dict(), "token": token}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""

    if not identifier or not password:
        return jsonify({"error": "username/email and password are required"}), 400

    user = User.query.filter(
        (User.username == identifier) | (User.email == identifier.lower())
    ).first()
    if user is None or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = generate_token(user)
    return jsonify({"user": user.to_dict(), "token": token}), 200


@auth_bp.route("/me", methods=["GET"])
@token_required
def me():
    return jsonify({"user": g.current_user.to_dict()}), 200
