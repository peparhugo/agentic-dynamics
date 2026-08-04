from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, current_user
from marshmallow import ValidationError

from app import db
from app.models import Widget
from app.schemas import (
    WidgetCreateSchema,
    WidgetUpdateSchema,
    PaginationSchema,
)
from app.pagination import paginate
from app.auth import admin_required
from app.middleware.audit import audit_log


widgets_v2_bp = Blueprint("widgets_v2", __name__)


@widgets_v2_bp.route("", methods=["GET"])
@jwt_required()
def list_widgets():
    page = paginate(Widget.query.order_by(Widget.id), PaginationSchema())
    page_dict = page.get_json()
    page_dict["version"] = "v2"
    return jsonify(page_dict), 200


@widgets_v2_bp.route("", methods=["POST"])
@jwt_required()
@audit_log("create_widget")
def create_widget():
    data = WidgetCreateSchema().load(request.get_json(silent=True) or {})
    widget = Widget(name=data["name"], description=data.get("description", ""),
                    owner_id=current_user.id)
    db.session.add(widget)
    db.session.commit()
    result = {"widget": widget.to_dict(), "version": "v2", "status": "created"}
    return jsonify(result), 201


@widgets_v2_bp.route("/<int:widget_id>", methods=["GET"])
@jwt_required()
def get_widget(widget_id):
    widget = db.session.get(Widget, widget_id)
    if not widget:
        return jsonify({"error": "Widget not found", "version": "v2"}), 404
    return jsonify({"widget": widget.to_dict(), "version": "v2"}), 200


@widgets_v2_bp.route("/<int:widget_id>", methods=["PATCH"])
@jwt_required()
@audit_log("update_widget")
def update_widget(widget_id):
    widget = db.session.get(Widget, widget_id)
    if not widget:
        return jsonify({"error": "Widget not found", "version": "v2"}), 404
    if widget.owner_id != current_user.id and current_user.role != "admin":
        return jsonify({"error": "Forbidden", "version": "v2"}), 403
    data = WidgetUpdateSchema().load(request.get_json(silent=True) or {})
    if "name" in data:
        widget.name = data["name"]
    if "description" in data:
        widget.description = data["description"]
    db.session.commit()
    return jsonify({"widget": widget.to_dict(), "version": "v2"}), 200


@widgets_v2_bp.route("/<int:widget_id>", methods=["DELETE"])
@jwt_required()
@audit_log("delete_widget")
def delete_widget(widget_id):
    widget = db.session.get(Widget, widget_id)
    if not widget:
        return jsonify({"error": "Widget not found", "version": "v2"}), 404
    if widget.owner_id != current_user.id and current_user.role != "admin":
        return jsonify({"error": "Forbidden", "version": "v2"}), 403
    db.session.delete(widget)
    db.session.commit()
    return jsonify({"message": "Widget deleted", "version": "v2"}), 200


@widgets_v2_bp.route("/admin/all", methods=["GET"])
@jwt_required()
@admin_required()
def admin_list_widgets():
    page = paginate(Widget.query.order_by(Widget.id), PaginationSchema())
    page_dict = page.get_json()
    page_dict["version"] = "v2"
    page_dict["note"] = "This admin-only endpoint is new in v2"
    return jsonify(page_dict), 200
