from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models import Item
from app.validators.schemas import ItemCreateSchema, ItemUpdateSchema, PaginationSchema
from app.utils.pagination import paginate

items_bp = Blueprint("items_v1", __name__)

item_create_schema = ItemCreateSchema()
item_update_schema = ItemUpdateSchema()
pagination_schema = PaginationSchema()


def _get_user_id():
    return int(get_jwt_identity())


@items_bp.route("", methods=["GET"])
@jwt_required()
def list_items():
    user_id = _get_user_id()

    errors = pagination_schema.validate(request.args)
    if errors:
        return jsonify({"error": "Invalid pagination parameters", "details": errors}), 400

    sort_by = request.args.get("sort_by", "created_at")
    order = request.args.get("order", "desc")
    name_filter = request.args.get("name", None)

    query = Item.query.filter_by(owner_id=user_id)

    if name_filter:
        query = query.filter(Item.name.ilike(f"%{name_filter}%"))

    sort_column = getattr(Item, sort_by, Item.created_at)
    if order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    result = paginate(query)
    return jsonify(result), 200


@items_bp.route("/<int:item_id>", methods=["GET"])
@jwt_required()
def get_item(item_id):
    user_id = _get_user_id()
    item = db.session.get(Item, item_id)

    if not item:
        return jsonify({"error": "Item not found"}), 404

    if item.owner_id != user_id:
        return jsonify({"error": "Forbidden"}), 403

    return jsonify({"data": item.to_dict()}), 200


@items_bp.route("", methods=["POST"])
@jwt_required()
def create_item():
    user_id = _get_user_id()
    json_data = request.get_json(silent=True) or {}

    errors = item_create_schema.validate(json_data)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    item = Item(
        name=json_data["name"],
        description=json_data.get("description"),
        owner_id=user_id,
    )
    db.session.add(item)
    db.session.commit()

    current_app.log_audit("create", "item", resource_id=item.id, user_id=user_id, status_code=201)

    return jsonify({"data": item.to_dict()}), 201


@items_bp.route("/<int:item_id>", methods=["PUT"])
@jwt_required()
def update_item(item_id):
    user_id = _get_user_id()
    item = db.session.get(Item, item_id)

    if not item:
        return jsonify({"error": "Item not found"}), 404

    if item.owner_id != user_id:
        return jsonify({"error": "Forbidden"}), 403

    json_data = request.get_json(silent=True) or {}

    errors = item_update_schema.validate(json_data)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    if "name" in json_data:
        item.name = json_data["name"]
    if "description" in json_data:
        item.description = json_data["description"]

    db.session.commit()

    current_app.log_audit("update", "item", resource_id=item.id, user_id=user_id, status_code=200)

    return jsonify({"data": item.to_dict()}), 200


@items_bp.route("/<int:item_id>", methods=["DELETE"])
@jwt_required()
def delete_item(item_id):
    user_id = _get_user_id()
    item = db.session.get(Item, item_id)

    if not item:
        return jsonify({"error": "Item not found"}), 404

    if item.owner_id != user_id:
        return jsonify({"error": "Forbidden"}), 403

    db.session.delete(item)
    db.session.commit()

    current_app.log_audit("delete", "item", resource_id=item_id, user_id=user_id, status_code=200)

    return jsonify({"message": "Item deleted"}), 200
