import datetime
import jwt
from app.extensions import db
from app.models.user import User
from app.middleware.auth import create_access_token


def register_user(username: str, email: str, password: str) -> tuple[dict, int]:
    if User.query.filter_by(username=username).first():
        return {"error": "Username already taken"}, 409
    if User.query.filter_by(email=email).first():
        return {"error": "Email already registered"}, 409

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return {
        "message": "User registered successfully",
        "user": user.to_dict(),
    }, 201


def login_user(username: str, password: str) -> tuple[dict, int]:
    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return {"error": "Invalid username or password"}, 401
    if not user.is_active:
        return {"error": "Account is deactivated"}, 403

    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "Bearer", "user": user.to_dict()}, 200
