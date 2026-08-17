import re

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)

from app.errors import APIError
from app.extensions import db
from app.models import User
from app.utils import require_fields

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    require_fields(data, ["username", "email", "password"])

    username = data["username"].strip()
    email = data["email"].strip().lower()
    password = data["password"]

    if len(username) < 3:
        raise APIError("username must be at least 3 characters", 400)
    if not EMAIL_RE.match(email):
        raise APIError("email is not a valid email address", 400)
    if len(password) < 6:
        raise APIError("password must be at least 6 characters", 400)

    if User.query.filter_by(username=username).first():
        raise APIError("username is already taken", 409)
    if User.query.filter_by(email=email).first():
        raise APIError("email is already registered", 409)

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return (
        jsonify(
            {
                "user": user.to_dict(),
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        ),
        201,
    )


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    require_fields(data, ["password"])

    if not data.get("username") and not data.get("email"):
        raise APIError("username or email is required", 400)

    query = User.query
    if data.get("username"):
        user = query.filter_by(username=data["username"].strip()).first()
    else:
        user = query.filter_by(email=data["email"].strip().lower()).first()

    if not user or not user.check_password(data["password"]):
        raise APIError("Invalid credentials", 401)

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify(
        {
            "user": user.to_dict(),
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
    )


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return jsonify({"access_token": access_token})


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    if not user:
        raise APIError("User not found", 404)
    return jsonify(user.to_dict())
