import bcrypt
from flask import request, jsonify, g

from app.api.v1 import bp
from app.api.v1.schemas import RegisterSchema, LoginSchema, RefreshSchema
from app.middleware.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    jwt_required,
)
from app.middleware.error_handler import APIError
from app.middleware.logging import audit_log
from app.models.user import create_user, find_user_by_username


@bp.route("/auth/register", methods=["POST"])
def register():
    data = RegisterSchema().load(request.get_json(silent=True) or {})
    if find_user_by_username(data["username"]):
        raise APIError("Username already taken", 409)

    hashed = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt()).decode()
    user = create_user(data["username"], hashed)

    audit_log("user_registered", username=user["username"])

    return (
        jsonify(
            {
                "user": {"id": user["id"], "username": user["username"]},
                "access_token": create_access_token(user["id"]),
                "refresh_token": create_refresh_token(user["id"]),
            }
        ),
        201,
    )


@bp.route("/auth/login", methods=["POST"])
def login():
    data = LoginSchema().load(request.get_json(silent=True) or {})
    user = find_user_by_username(data["username"])
    if not user or not bcrypt.checkpw(
        data["password"].encode(), user["password"].encode()
    ):
        raise APIError("Invalid credentials", 401)

    audit_log("user_login", username=user["username"])

    return jsonify(
        {
            "user": {"id": user["id"], "username": user["username"]},
            "access_token": create_access_token(user["id"]),
            "refresh_token": create_refresh_token(user["id"]),
        }
    )


@bp.route("/auth/refresh", methods=["POST"])
def refresh():
    data = RefreshSchema().load(request.get_json(silent=True) or {})
    payload = decode_token(data["refresh_token"])
    if payload.get("type") != "refresh":
        raise APIError("Token is not a refresh token", 401)

    access_token = create_access_token(payload["sub"])
    refresh_token = create_refresh_token(payload["sub"])

    return jsonify({"access_token": access_token, "refresh_token": refresh_token})


@bp.route("/auth/me", methods=["GET"])
@jwt_required
def me():
    user = g.current_user
    return jsonify({"user": {"id": user["id"], "username": user["username"]}})
