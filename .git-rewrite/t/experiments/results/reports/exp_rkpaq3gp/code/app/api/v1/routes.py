from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app import db
from app.models.item import Item
from app.utils.validators import item_create_schema, item_update_schema, pagination_schema
from app.utils.pagination import paginate
from app.middleware.audit import log_audit_event

api_v1_bp = Blueprint("api_v1", __name__)


@api_v1_bp.route("/items", methods=["GET"])
@jwt_required()
def list_items():
    try:
        params = pagination_schema.load(request.args)
    except ValidationError as exc:
        return jsonify({"error": "Validation failed", "details": exc.messages}), 422

    query = Item.query.order_by(Item.created_at.desc())
    result = paginate(query, page=params["page"], per_page=params["per_page"])
    return jsonify(result), 200


@api_v1_bp.route("/items/<int:item_id>", methods=["GET"])
@jwt_required()
def get_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404
    return jsonify({"item": item.to_dict()}), 200


@api_v1_bp.route("/items", methods=["POST"])
@jwt_required()
def create_item():
    try:
        data = item_create_schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": "Validation failed", "details": exc.messages}), 422

    identity = get_jwt_identity()
    item = Item(name=data["name"], description=data.get("description", ""), owner_id=int(identity))
    db.session.add(item)
    db.session.commit()

    log_audit_event("item_created", user_id=int(identity), resource="item", resource_id=str(item.id), status_code=201)

    return jsonify({"item": item.to_dict()}), 201


@api_v1_bp.route("/items/<int:item_id>", methods=["PUT"])
@jwt_required()
def update_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404

    try:
        data = item_update_schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": "Validation failed", "details": exc.messages}), 422

    identity = get_jwt_identity()
    if item.owner_id != int(identity):
        return jsonify({"error": "Forbidden"}), 403

    for key, value in data.items():
        if value is not None:
            setattr(item, key, value)
    db.session.commit()

    log_audit_event("item_updated", user_id=int(identity), resource="item", resource_id=str(item.id), status_code=200)

    return jsonify({"item": item.to_dict()}), 200


@api_v1_bp.route("/items/<int:item_id>", methods=["DELETE"])
@jwt_required()
def delete_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404

    identity = get_jwt_identity()
    if item.owner_id != int(identity):
        return jsonify({"error": "Forbidden"}), 403

    db.session.delete(item)
    db.session.commit()

    log_audit_event("item_deleted", user_id=int(identity), resource="item", resource_id=str(item_id), status_code=200)

    return jsonify({"message": "Item deleted"}), 200
