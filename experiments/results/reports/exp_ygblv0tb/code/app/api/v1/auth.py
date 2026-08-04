from flask import jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)

from ...audit import record_audit
from ...errors import ApiError
from ...extensions import db, limiter
from ...models import User
from ...schemas import LoginSchema, RegisterSchema
from . import api_v1


def _json_body():
    data = request.get_json(silent=True)
    if data is None:
        raise ApiError("Request body must be valid JSON", 400)
    return data


@api_v1.post("/auth/register")
@limiter.limit("10 per minute")
def register():
    data = RegisterSchema().load(_json_body())

    if User.query.filter_by(email=data["email"]).first():
        raise ApiError("A user with that email already exists", 409)

    user = User(email=data["email"])
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    record_audit("user.register", 201, user_id=user.id)
    return jsonify({"user": user.to_dict()}), 201


@api_v1.post("/auth/login")
@limiter.limit("10 per minute")
def login():
    data = LoginSchema().load(_json_body())

    user = User.query.filter_by(email=data["email"]).first()
    if user is None or not user.check_password(data["password"]):
        record_audit("user.login_failed", 401,
                     detail=f"email={data['email']}")
        raise ApiError("Invalid email or password", 401)

    record_audit("user.login", 200, user_id=user.id)
    return jsonify({
        "access_token": create_access_token(identity=str(user.id)),
        "refresh_token": create_refresh_token(identity=str(user.id)),
        "token_type": "Bearer",
    })


@api_v1.post("/auth/refresh")
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    record_audit("user.token_refresh", 200, user_id=int(identity))
    return jsonify({
        "access_token": create_access_token(identity=identity),
        "token_type": "Bearer",
    })


@api_v1.get("/auth/me")
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None:
        raise ApiError("User no longer exists", 401)
    return jsonify({"user": user.to_dict()})
