from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from marshmallow import ValidationError
from app.models.user import User
from app.extensions import db
from app.middleware import jwt_required, admin_required, rate_limit
from app.utils import UserCreateSchema, UserUpdateSchema, LoginSchema, paginate_query, log_audit

v2 = Blueprint("v2", __name__, url_prefix="/api/v2")


@v2.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": "v2"})


@v2.route("/auth/login", methods=["POST"])
@rate_limit("30 per minute")
def login():
    schema = LoginSchema()
    try:
        data = schema.load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({"error": "Validation Error", "messages": e.messages}), 422

    user = User.query.filter_by(username=data["username"]).first()
    if not user or not check_password_hash(user.password_hash, data["password"]):
        log_audit("login_failed", "user", details={"username": data.get("username")}, status="failure")
        return jsonify({"error": "Unauthorized", "message": "Invalid credentials"}), 401

    token = create_access_token(identity={"id": user.id, "username": user.username, "role": "user"})
    log_audit("login", "user", user.id, status="success")
    return jsonify({"access_token": token, "token_type": "Bearer", "expires_in": 3600}), 200


@v2.route("/users", methods=["GET"])
@jwt_required
@rate_limit("200 per minute")
def get_users():
    query = User.query.filter_by(is_active=True).order_by(User.id)
    result = paginate_query(query)
    current_user = get_jwt_identity()
    log_audit("list_users", "user", details={"page": result["pagination"]["page"]}, status="success")
    return jsonify(result), 200


@v2.route("/users/<int:user_id>", methods=["GET"])
@jwt_required
@rate_limit("200 per minute")
def get_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Not Found", "message": f"User {user_id} not found"}), 404
    return jsonify({"data": user.to_dict()}), 200


@v2.route("/users", methods=["POST"])
@admin_required
@rate_limit("50 per minute")
def create_user():
    schema = UserCreateSchema()
    try:
        data = schema.load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({"error": "Validation Error", "messages": e.messages}), 422

    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "Conflict", "message": "Username already exists"}), 409
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Conflict", "message": "Email already exists"}), 409

    user = User(
        username=data["username"],
        email=data["email"],
        password_hash=generate_password_hash(data["password_hash"]),
    )
    db.session.add(user)
    db.session.commit()

    log_audit("create", "user", user.id, {"username": user.username}, status="success")
    return jsonify({"data": user.to_dict()}), 201


@v2.route("/users/<int:user_id>", methods=["PUT"])
@jwt_required
@rate_limit("50 per minute")
def update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Not Found", "message": f"User {user_id} not found"}), 404

    current_user = get_jwt_identity()
    if current_user["id"] != user_id and current_user.get("role") != "admin":
        return jsonify({"error": "Forbidden", "message": "You can only update your own profile"}), 403

    schema = UserUpdateSchema(partial=False)
    try:
        data = schema.load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({"error": "Validation Error", "messages": e.messages}), 422

    if "username" in data:
        existing = User.query.filter(User.username == data["username"], User.id != user_id).first()
        if existing:
            return jsonify({"error": "Conflict", "message": "Username already exists"}), 409
        user.username = data["username"]

    if "email" in data:
        existing = User.query.filter(User.email == data["email"], User.id != user_id).first()
        if existing:
            return jsonify({"error": "Conflict", "message": "Email already exists"}), 409
        user.email = data["email"]

    if "password_hash" in data:
        user.password_hash = generate_password_hash(data["password_hash"])

    if "is_active" in data and current_user.get("role") == "admin":
        user.is_active = data["is_active"]

    db.session.commit()
    log_audit("update", "user", user.id, {"username": user.username}, status="success")
    return jsonify({"data": user.to_dict()}), 200


@v2.route("/users/<int:user_id>", methods=["DELETE"])
@admin_required
@rate_limit("30 per minute")
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Not Found", "message": f"User {user_id} not found"}), 404

    db.session.delete(user)
    db.session.commit()
    log_audit("delete", "user", user_id, {"username": user.username}, status="success")
    return jsonify({"message": f"User {user_id} deleted"}), 200
