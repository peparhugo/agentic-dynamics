from flask import Blueprint, request, g

from auth import hash_password, verify_password, create_token, login_required
from models import db, User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data:
        return {"error": "Request body must be JSON"}, 400

    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    errors = []
    if not username:
        errors.append("username is required")
    if not email:
        errors.append("email is required")
    if not password:
        errors.append("password is required")
    elif len(password) < 6:
        errors.append("password must be at least 6 characters")
    if errors:
        return {"error": "; ".join(errors)}, 400

    if User.query.filter_by(username=username).first():
        return {"error": "Username already taken"}, 409
    if User.query.filter_by(email=email).first():
        return {"error": "Email already registered"}, 409

    user = User(username=username, email=email, password_hash=hash_password(password))
    db.session.add(user)
    db.session.commit()

    token = create_token(user.id)
    return {"user": user.to_dict(), "token": token}, 201


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return {"error": "Request body must be JSON"}, 400

    identifier = data.get("username") or data.get("email") or ""
    password = data.get("password", "")

    if not identifier or not password:
        return {"error": "username/email and password are required"}, 400

    user = User.query.filter(
        (User.username == identifier) | (User.email == identifier)
    ).first()

    if user is None or not verify_password(password, user.password_hash):
        return {"error": "Invalid credentials"}, 401

    token = create_token(user.id)
    return {"user": user.to_dict(), "token": token}, 200


@auth_bp.route("/api/auth/me", methods=["GET"])
@login_required
def me():
    return {"user": g.current_user.to_dict()}, 200
