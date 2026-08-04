"""Authentication endpoints: register, login, refresh, current user."""
from flask import request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)

from app.api.v1 import api_v1
from app.audit import audit
from app.errors import APIError
from app.extensions import db, limiter
from app.models import User
from app.schemas import LoginSchema, RegisterSchema


def _json_body() -> dict:
    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        raise APIError("Request body must be a JSON object.", 400)
    return data


@api_v1.post("/auth/register")
@limiter.limit("10 per minute")
def register():
    data = RegisterSchema().load(_json_body())

    if User.query.filter((User.username == data["username"]) | (User.email == data["email"])).first():
        raise APIError("A user with that username or email already exists.", 409)

    user = User(username=data["username"], email=data["email"])
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    audit("user.register", user_id=user.id, resource_type="user", resource_id=user.id, status_code=201)
    return {"data": user.to_dict()}, 201


@api_v1.post("/auth/login")
@limiter.limit("5 per minute")
def login():
    data = LoginSchema().load(_json_body())

    user = User.query.filter_by(username=data["username"]).first()
    if user is None or not user.check_password(data["password"]):
        audit("auth.login.failure", detail=f"username={data['username']}", status_code=401)
        raise APIError("Invalid username or password.", 401)
    if not user.is_active:
        audit("auth.login.failure", user_id=user.id, detail="inactive account", status_code=403)
        raise APIError("Account is deactivated.", 403)

    identity = str(user.id)
    access_token = create_access_token(identity=identity)
    refresh_token = create_refresh_token(identity=identity)

    audit("auth.login.success", user_id=user.id, status_code=200)
    return {
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
        }
    }


@api_v1.post("/auth/refresh")
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    audit("auth.token.refresh", user_id=int(identity), status_code=200)
    return {"data": {"access_token": access_token, "token_type": "Bearer"}}


@api_v1.get("/auth/me")
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None:
        raise APIError("User no longer exists.", 401)
    return {"data": user.to_dict()}
