from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from .db import db
from .errors import ApiError
from .models import User

bp = Blueprint("auth", __name__, url_prefix="/api")


def _now():
    return datetime.now(timezone.utc)


def create_token(user_id):
    payload = {
        "sub": user_id,
        "iat": _now(),
        "exp": _now() + timedelta(seconds=current_app.config["JWT_EXPIRY_SECONDS"]),
    }
    return jwt.encode(
        payload,
        current_app.config["SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )


def get_token():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):]
    return None


def decode_token(token):
    try:
        return jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
    except jwt.ExpiredSignatureError:
        raise ApiError("token has expired", 401)
    except jwt.InvalidTokenError:
        raise ApiError("invalid token", 401)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = get_token()
        if not token:
            raise ApiError("authentication required", 401)
        payload = decode_token(token)
        user = db.session.get(User, payload.get("sub"))
        if user is None:
            raise ApiError("invalid token", 401)
        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


def _validate_credentials(data):
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    errors = {}
    if not username:
        errors["username"] = "required"
    if not email or "@" not in email:
        errors["email"] = "must be a valid email"
    if not password:
        errors["password"] = "required"
    elif len(password) < 8:
        errors["password"] = "must be at least 8 characters"
    if errors:
        raise ApiError("invalid registration data", 400, errors)
    return username, email, password


@bp.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        raise ApiError("invalid JSON body", 400)
    username, email, password = _validate_credentials(data)

    if User.query.filter_by(username=username).first():
        raise ApiError("username already taken", 409, {"username": "exists"})
    if User.query.filter_by(email=email).first():
        raise ApiError("email already registered", 409, {"email": "exists"})

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError("username or email already taken", 409)

    return jsonify({"token": create_token(user.id), "user": user.to_dict()}), 201


@bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        raise ApiError("invalid JSON body", 400)
    identifier = (data.get("identifier") or "").strip().lower()
    password = data.get("password") or ""
    if not identifier or not password:
        raise ApiError("identifier and password are required", 400)

    user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
    if user is None or not user.check_password(password):
        raise ApiError("invalid credentials", 401)

    return jsonify({"token": create_token(user.id), "user": user.to_dict()})


@bp.get("/auth/me")
@login_required
def me():
    return jsonify(g.current_user.to_dict())
