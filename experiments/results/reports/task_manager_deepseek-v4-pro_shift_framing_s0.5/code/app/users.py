from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from .extensions import db
from .models import User
from .utils import error_response

users_bp = Blueprint("users", __name__, url_prefix="/users")


@users_bp.get("")
@jwt_required()
def list_users():
    users = User.query.order_by(User.id).all()
    return {"users": [u.to_dict() for u in users]}, 200


@users_bp.get("/<int:user_id>")
@jwt_required()
def get_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return error_response("user not found", 404)
    return {"user": user.to_dict()}, 200
