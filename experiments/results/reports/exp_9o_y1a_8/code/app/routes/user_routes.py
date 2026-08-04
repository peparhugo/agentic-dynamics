from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app.models import db, User
from app.utils import get_current_user, paginate_query
from app.schemas import PaginationSchema
from marshmallow import ValidationError

user_bp = Blueprint("users", __name__)


@user_bp.route("/me", methods=["GET"])
@jwt_required()
def get_me():
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found."}), 404
    return jsonify(user.to_dict()), 200


@user_bp.route("", methods=["GET"])
@jwt_required()
def list_users():
    try:
        params = PaginationSchema().load(request.args)
    except ValidationError as err:
        return jsonify({"error": "Validation failed.", "details": err.messages}), 400

    query = User.query.order_by(User.username.asc())
    result = paginate_query(query, page=params["page"], per_page=params["per_page"])
    return jsonify(result), 200


@user_bp.route("/<user_id>", methods=["GET"])
@jwt_required()
def get_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404
    return jsonify(user.to_dict()), 200
