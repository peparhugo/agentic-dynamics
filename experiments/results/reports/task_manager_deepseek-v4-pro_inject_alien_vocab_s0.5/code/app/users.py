from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from .models import User

users_bp = Blueprint("users", __name__, url_prefix="/api/users")


@users_bp.route("", methods=["GET"])
@jwt_required()
def list_users():
    users = User.query.order_by(User.username.asc()).all()
    return jsonify({"users": [u.to_dict() for u in users]}), 200
