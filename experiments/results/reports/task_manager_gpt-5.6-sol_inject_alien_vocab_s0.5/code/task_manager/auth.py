from flask import Blueprint, jsonify
from flask_jwt_extended import create_access_token, jwt_required

from task_manager import db
from task_manager.models import User
from task_manager.utils import current_user, json_body, json_error


auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    data = json_body()
    if not isinstance(data, dict):
        return json_error("A JSON object is required")

    username = data.get("username", "").strip() if isinstance(data.get("username", ""), str) else ""
    email = data.get("email", "").strip().lower() if isinstance(data.get("email", ""), str) else ""
    password = data.get("password", "")
    if not username or not email or not isinstance(password, str):
        return json_error("username, email, and password are required")
    if len(username) > 80:
        return json_error("username must not exceed 80 characters")
    if "@" not in email or len(email) > 255:
        return json_error("A valid email is required")
    if len(password) < 8:
        return json_error("password must contain at least 8 characters")
    if User.query.filter_by(username=username).first():
        return json_error("username is already registered", 409)
    if User.query.filter_by(email=email).first():
        return json_error("email is already registered", 409)

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    token = create_access_token(identity=str(user.id))
    return jsonify(access_token=token, user=user.to_dict()), 201


@auth_bp.post("/login")
def login():
    data = json_body()
    if not isinstance(data, dict):
        return json_error("A JSON object is required")
    login_value = data.get("email") or data.get("username")
    password = data.get("password")
    if not isinstance(login_value, str) or not isinstance(password, str):
        return json_error("email or username and password are required")

    user = User.query.filter(
        (User.email == login_value.strip().lower()) | (User.username == login_value.strip())
    ).first()
    if not user or not user.check_password(password):
        return json_error("Invalid credentials", 401)
    token = create_access_token(identity=str(user.id))
    return jsonify(access_token=token, user=user.to_dict())


@auth_bp.get("/me")
@jwt_required()
def me():
    user = current_user()
    if not user:
        return json_error("User no longer exists", 401)
    return jsonify(user=user.to_dict())
