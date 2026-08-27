from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from .audit import log_action
from .errors import ForbiddenError, NotFoundError
from .extensions import db
from .models import Item, User
from .pagination import paginate
from .validation import get_json_body, raise_for_errors, validate_item

items_bp = Blueprint("items", __name__)


def _current_user():
    identity = get_jwt_identity()
    return db.session.get(User, int(identity))


@items_bp.route("/items", methods=["GET"])
@jwt_required()
def list_items():
    query = Item.query.order_by(Item.id.asc())
    items, meta = paginate(query)
    return jsonify({"items": [i.to_dict() for i in items], **meta}), 200


@items_bp.route("/items", methods=["POST"])
@jwt_required()
def create_item():
    user = _current_user()
    data = get_json_body()
    errors = validate_item(data, partial=False)
    raise_for_errors(errors)

    item = Item(
        name=data["name"].strip(),
        description=data.get("description"),
        owner_id=user.id,
    )
    db.session.add(item)
    db.session.commit()

    log_action(
        "create", "item", resource_id=item.id, user_id=user.id, details=item.to_dict()
    )

    return jsonify({"item": item.to_dict()}), 201


@items_bp.route("/items/<int:item_id>", methods=["GET"])
@jwt_required()
def get_item(item_id):
    item = db.session.get(Item, item_id)
    if item is None:
        raise NotFoundError("Item not found.")
    return jsonify({"item": item.to_dict()}), 200


@items_bp.route("/items/<int:item_id>", methods=["PUT", "PATCH"])
@jwt_required()
def update_item(item_id):
    user = _current_user()
    item = db.session.get(Item, item_id)
    if item is None:
        raise NotFoundError("Item not found.")
    if item.owner_id != user.id:
        raise ForbiddenError("You do not own this item.")

    data = get_json_body()
    partial = request.method == "PATCH"
    errors = validate_item(data, partial=partial)
    raise_for_errors(errors)

    before = item.to_dict()
    if "name" in data and data["name"] is not None:
        item.name = data["name"].strip()
    if "description" in data:
        item.description = data["description"]

    db.session.commit()

    log_action(
        "update",
        "item",
        resource_id=item.id,
        user_id=user.id,
        details={"before": before, "after": item.to_dict()},
    )

    return jsonify({"item": item.to_dict()}), 200


@items_bp.route("/items/<int:item_id>", methods=["DELETE"])
@jwt_required()
def delete_item(item_id):
    user = _current_user()
    item = db.session.get(Item, item_id)
    if item is None:
        raise NotFoundError("Item not found.")
    if item.owner_id != user.id:
        raise ForbiddenError("You do not own this item.")

    db.session.delete(item)
    db.session.commit()

    log_action(
        "delete", "item", resource_id=item_id, user_id=user.id
    )

    return jsonify({"message": "Item deleted."}), 200
