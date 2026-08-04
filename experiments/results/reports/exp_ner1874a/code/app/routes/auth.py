from datetime import timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token
from flask_limiter.util import get_remote_address

from ..extensions import limiter

bp = Blueprint("auth", __name__)


# Demo in-memory user; in real apps use a database and hashed passwords
_DEMO_USER = {"id": 1, "username": "admin", "password": "password"}


@bp.post("/login")
@limiter.limit("10 per minute", key_func=get_remote_address)
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if username != _DEMO_USER["username"] or password != _DEMO_USER["password"]:
        return jsonify({"error": {"type": "AuthError", "message": "Invalid credentials"}}), 401

    access_token = create_access_token(identity=_DEMO_USER["id"], expires_delta=timedelta(hours=1))
    return jsonify({"access_token": access_token, "token_type": "Bearer"})
