from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    current_user,
)
from marshmallow import ValidationError

from app import db
from app.models import User, Widget
from app.schemas import (
    RegisterSchema,
    LoginSchema,
    UserUpdateSchema,
    WidgetCreateSchema,
    WidgetUpdateSchema,
    PaginationSchema,
)
from app.pagination import paginate
from app.auth import admin_required
from app.middleware.audit import audit_log


users_bp = Blueprint("users_v1", __name__)
widgets_bp = Blueprint("widgets_v1", __name__)

# ─── Auth routes ──────────────────────────────────────────────────────────────

@users_bp.route("/auth/register", methods=["POST"])
@audit_log("register")
def register():
    data = RegisterSchema().load(request.get_json(silent=True) or {})
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already registered"}), 409
    user = User(name=data["name"], email=data["email"], role="user")
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    token = create_access_token(identity=str(user.id))
    return jsonify({"user": user.to_dict(), "token": token}), 201


@users_bp.route("/auth/login", methods=["POST"])
@audit_log("login")
def login():
    data = LoginSchema().load(request.get_json(silent=True) or {})
    user = User.query.filter_by(email=data["email"]).first()
    if not user or not user.check_password(data["password"]):
        return jsonify({"error": "Invalid email or password"}), 401
    token = create_access_token(identity=str(user.id))
    return jsonify({"user": user.to_dict(), "token": token}), 200


# ─── User routes ──────────────────────────────────────────────────────────────

@users_bp.route("/users/me", methods=["GET"])
@jwt_required()
def get_me():
    return jsonify({"user": current_user.to_dict()}), 200


@users_bp.route("/users/me", methods=["PATCH"])
@jwt_required()
@audit_log("update_profile")
def update_me():
    data = UserUpdateSchema().load(request.get_json(silent=True) or {})
    if "name" in data:
        current_user.name = data["name"]
    if "password" in data:
        current_user.set_password(data["password"])
    db.session.commit()
    return jsonify({"user": current_user.to_dict()}), 200


@users_bp.route("/users", methods=["GET"])
@jwt_required()
@admin_required()
def list_users():
    return paginate(User.query.order_by(User.id), PaginationSchema())


@users_bp.route("/users/<int:user_id>", methods=["GET"])
@jwt_required()
@admin_required()
def get_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": user.to_dict()}), 200


@users_bp.route("/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
@admin_required()
@audit_log("delete_user")
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted"}), 200


# ─── Widget CRUD (v1) ────────────────────────────────────────────────────────

@widgets_bp.route("", methods=["GET"])
@jwt_required()
def list_widgets():
    return paginate(Widget.query.order_by(Widget.id), PaginationSchema())


@widgets_bp.route("", methods=["POST"])
@jwt_required()
@audit_log("create_widget")
def create_widget():
    data = WidgetCreateSchema().load(request.get_json(silent=True) or {})
    widget = Widget(name=data["name"], description=data.get("description", ""),
                    owner_id=current_user.id)
    db.session.add(widget)
    db.session.commit()
    return jsonify({"widget": widget.to_dict()}), 201


@widgets_bp.route("/<int:widget_id>", methods=["GET"])
@jwt_required()
def get_widget(widget_id):
    widget = db.session.get(Widget, widget_id)
    if not widget:
        return jsonify({"error": "Widget not found"}), 404
    return jsonify({"widget": widget.to_dict()}), 200


@widgets_bp.route("/<int:widget_id>", methods=["PUT"])
@jwt_required()
@audit_log("update_widget")
def update_widget(widget_id):
    widget = db.session.get(Widget, widget_id)
    if not widget:
        return jsonify({"error": "Widget not found"}), 404
    if widget.owner_id != current_user.id and current_user.role != "admin":
        return jsonify({"error": "Forbidden"}), 403
    data = WidgetUpdateSchema().load(request.get_json(silent=True) or {})
    if "name" in data:
        widget.name = data["name"]
    if "description" in data:
        widget.description = data["description"]
    db.session.commit()
    return jsonify({"widget": widget.to_dict()}), 200


@widgets_bp.route("/<int:widget_id>", methods=["DELETE"])
@jwt_required()
@audit_log("delete_widget")
def delete_widget(widget_id):
    widget = db.session.get(Widget, widget_id)
    if not widget:
        return jsonify({"error": "Widget not found"}), 404
    if widget.owner_id != current_user.id and current_user.role != "admin":
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(widget)
    db.session.commit()
    return jsonify({"message": "Widget deleted"}), 200
