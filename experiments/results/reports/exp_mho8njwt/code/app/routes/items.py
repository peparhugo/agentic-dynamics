from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.extensions import db
from app.models.item import Item
from app.schemas.item import ItemCreateSchema, ItemUpdateSchema
from app.utils.pagination import paginate_query
from app.utils.audit import log_audit

items_bp = Blueprint("items", __name__)


@items_bp.route("", methods=["GET"])
@jwt_required()
def list_items():
    query = Item.query.order_by(Item.id)
    return paginate_query(query)


@items_bp.route("/<int:item_id>", methods=["GET"])
@jwt_required()
def get_item(item_id):
    item = Item.query.get(item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404
    return jsonify(item.to_dict()), 200


@items_bp.route("", methods=["POST"])
@jwt_required()
def create_item():
    schema = ItemCreateSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "details": err.messages}), 422

    user_id = int(get_jwt_identity())
    item = Item(name=data["name"], description=data.get("description"), user_id=user_id)
    db.session.add(item)
    db.session.commit()

    log_audit("create", "item", item.id, {"name": item.name, "user_id": user_id}, user_id=user_id)

    return jsonify(item.to_dict()), 201


@items_bp.route("/<int:item_id>", methods=["PUT"])
@jwt_required()
def update_item(item_id):
    user_id = int(get_jwt_identity())
    item = Item.query.get(item_id)

    if not item:
        return jsonify({"error": "Item not found"}), 404

    if item.user_id != user_id:
        return jsonify({"error": "Forbidden"}), 403

    schema = ItemUpdateSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "details": err.messages}), 422

    old_values = {"name": item.name, "description": item.description}

    if "name" in data:
        item.name = data["name"]
    if "description" in data:
        item.description = data["description"]

    db.session.commit()

    new_values = {"name": item.name, "description": item.description}
    log_audit("update", "item", item.id, {"old": old_values, "new": new_values}, user_id=user_id)

    return jsonify(item.to_dict()), 200


@items_bp.route("/<int:item_id>", methods=["DELETE"])
@jwt_required()
def delete_item(item_id):
    user_id = int(get_jwt_identity())
    item = Item.query.get(item_id)

    if not item:
        return jsonify({"error": "Item not found"}), 404

    if item.user_id != user_id:
        return jsonify({"error": "Forbidden"}), 403

    db.session.delete(item)
    db.session.commit()

    log_audit("delete", "item", item_id, {"name": item.name}, user_id=user_id)

    return jsonify({"message": "Item deleted"}), 200
