from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from task_manager.models import User


users_bp = Blueprint("users", __name__)


@users_bp.get("")
@jwt_required()
def list_users():
    users = User.query.order_by(User.username.asc()).all()
    return jsonify(users=[user.to_dict() for user in users])
