from flask import Blueprint, request, g
from app import db, limiter
from app.models.user import User
from app.models.item import Item
from app.auth.jwt import create_access_token, login_required
from app.middleware.audit import audit_log
from app.validators import (
    RegisterSchema, LoginSchema, UserUpdateSchema,
    ItemSchema, ItemUpdateSchema, validate_and_load,
)
from app.utils import paginate_query

bp = Blueprint("v2", __name__)


@bp.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "version": "2.0"}


@bp.route("/register", methods=["POST"])
@limiter.limit("5 per hour")
@audit_log("register")
@validate_and_load(RegisterSchema)
def register(validated_data):
    if User.query.filter_by(email=validated_data["email"]).first():
        return {"error": "Email already registered"}, 409
    if User.query.filter_by(username=validated_data["username"]).first():
        return {"error": "Username already taken"}, 409
    user = User(
        username=validated_data["username"],
        email=validated_data["email"],
    )
    user.set_password(validated_data["password"])
    db.session.add(user)
    db.session.commit()
    return {"message": "User registered", "user": user.to_dict()}, 201


@bp.route("/login", methods=["POST"])
@limiter.limit("10 per hour")
@audit_log("login")
@validate_and_load(LoginSchema)
def login(validated_data):
    user = User.query.filter_by(email=validated_data["email"]).first()
    if not user or not user.check_password(validated_data["password"]):
        return {"error": "Invalid email or password"}, 401
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "Bearer"}, 200


@bp.route("/users/me", methods=["GET"])
@login_required
@audit_log("get_profile")
def get_profile():
    user = g.current_user
    return {"user": user.to_dict(), "role": "standard"}, 200


@bp.route("/users/me", methods=["PUT"])
@login_required
@audit_log("update_profile")
@validate_and_load(UserUpdateSchema)
def update_profile(validated_data):
    user = g.current_user
    if "username" in validated_data:
        existing = User.query.filter(
            User.username == validated_data["username"], User.id != user.id
        ).first()
        if existing:
            return {"error": "Username already taken"}, 409
        user.username = validated_data["username"]
    if "email" in validated_data:
        existing = User.query.filter(
            User.email == validated_data["email"], User.id != user.id
        ).first()
        if existing:
            return {"error": "Email already registered"}, 409
        user.email = validated_data["email"]
    if "password" in validated_data:
        user.set_password(validated_data["password"])
    db.session.commit()
    user_data = user.to_dict()
    user_data["role"] = "standard"
    return {"user": user_data}, 200


@bp.route("/items", methods=["GET"])
@login_required
@audit_log("list_items")
def list_items():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)
    query = Item.query.order_by(Item.id.desc())
    if request.args.get("q"):
        query = query.filter(Item.name.ilike(f"%{request.args['q']}%"))
    result = paginate_query(query, page, per_page)
    result["meta"] = {"api_version": "2.0"}
    return result, 200


@bp.route("/items/<int:item_id>", methods=["GET"])
@login_required
@audit_log("get_item")
def get_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        return {"error": "Not found"}, 404
    return {"data": item.to_dict(), "meta": {"api_version": "2.0"}}, 200


@bp.route("/items", methods=["POST"])
@login_required
@audit_log("create_item")
@validate_and_load(ItemSchema)
def create_item(validated_data):
    item = Item(**validated_data)
    db.session.add(item)
    db.session.commit()
    return {"data": item.to_dict(), "meta": {"api_version": "2.0"}}, 201


@bp.route("/items/<int:item_id>", methods=["PUT"])
@login_required
@audit_log("update_item")
@validate_and_load(ItemUpdateSchema)
def update_item(item_id, validated_data):
    item = db.session.get(Item, item_id)
    if not item:
        return {"error": "Not found"}, 404
    if "name" in validated_data:
        item.name = validated_data["name"]
    if "description" in validated_data:
        item.description = validated_data["description"]
    db.session.commit()
    return {"data": item.to_dict(), "meta": {"api_version": "2.0"}}, 200


@bp.route("/items/<int:item_id>", methods=["DELETE"])
@login_required
@audit_log("delete_item")
def delete_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        return {"error": "Not found"}, 404
    db.session.delete(item)
    db.session.commit()
    return {"message": "Deleted", "meta": {"api_version": "2.0"}}, 200
