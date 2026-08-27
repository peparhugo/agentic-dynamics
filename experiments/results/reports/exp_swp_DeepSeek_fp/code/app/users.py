from flask import Blueprint, jsonify

from .decorators import token_required
from .errors import APIError
from .extensions import db
from .models import User
from .validators import get_pagination

users_bp = Blueprint("users", __name__)


@users_bp.route("", methods=["GET"])
@token_required
def list_users():
    page, per_page = get_pagination()
    query = User.query
    total = query.count()
    users = query.order_by(User.id.asc()).offset((page - 1) * per_page).limit(per_page).all()
    pages = (total + per_page - 1) // per_page
    return jsonify(
        {
            "data": [u.to_dict() for u in users],
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
        }
    ), 200


@users_bp.route("/<int:user_id>", methods=["GET"])
@token_required
def get_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        raise APIError("User not found", 404, "not_found")
    return jsonify(user.to_dict()), 200
