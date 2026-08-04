from __future__ import annotations

from flask import Blueprint, request
from flask_jwt_extended import create_access_token

from ..schemas import LoginSchema
from ..errors import ValidationError
from ..extensions import limiter


bp = Blueprint("auth", __name__)


# Simple hard-coded user store for demo purposes
USERS = {
    "admin": {
        "password": "password",  # Do NOT use plain text in real apps
        "roles": ["admin"],
    },
    "user": {
        "password": "password",
        "roles": ["user"],
    },
}


@bp.post("/login")
@limiter.limit("5 per minute")
def login():
    json_data = request.get_json(silent=True) or {}
    data = LoginSchema().load(json_data)  # raises marshmallow.ValidationError
    username = data["username"]
    password = data["password"]

    user = USERS.get(username)
    if not user or user["password"] != password:
        # Avoid user enumeration by generic message
        return {"error": {"message": "Invalid credentials"}}, 401

    token = create_access_token(identity=username, additional_claims={"roles": user.get("roles", [])})
    return {"access_token": token}
