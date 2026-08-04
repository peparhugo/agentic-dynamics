from functools import wraps

from flask import jsonify, current_user
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.models import User
from app import db


def admin_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            if current_user.role != "admin":
                return jsonify({"error": "Admin access required"}), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper


def register_jwt_handlers(jwt):
    @jwt.user_identity_loader
    def user_identity_lookup(user_id):
        return user_id

    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        identity = jwt_data["sub"]
        return db.session.get(User, int(identity))
