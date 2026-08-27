from flask import Blueprint, g, jsonify, request

from .audit import log_action
from .auth_utils import token_required
from .errors import NotFoundError
from .extensions import db
from .models import Item
from .pagination import paginate
from .validation import validate_item_payload

items_bp = Blueprint("items", __name__, url_prefix="/v1/items")


@items_bp.get("")
@token_required
def list_items():
    query = Item.query.filter_by(owner_id=g.current_user.id).order_by(Item.id.asc())
    return jsonify(paginate(query, request.args)), 200


@items_bp.post("")
@token_required
def create_item():
    payload = validate_item_payload(request.get_json(silent=True))
    item = Item(
        name=payload["name"],
        description=payload["description"],
        owner_id=g.current_user.id,
    )
    db.session.add(item)
    db.session.flush()
    log_action(
        g.current_user.id,
        "create",
        "item",
        item.id,
        {"name": item.name, "description": item.description},
    )
    db.session.commit()
    return jsonify(item.to_dict()), 201


@items_bp.get("/<int:item_id>")
@token_required
def get_item(item_id):
    item = _get_owned_item(item_id)
    return jsonify(item.to_dict()), 200


@items_bp.put("/<int:item_id>")
@token_required
def update_item(item_id):
    item = _get_owned_item(item_id)
    payload = validate_item_payload(request.get_json(silent=True))
    item.name = payload["name"]
    item.description = payload["description"]
    db.session.flush()
    log_action(
        g.current_user.id,
        "update",
        "item",
        item.id,
        {"name": item.name, "description": item.description},
    )
    db.session.commit()
    return jsonify(item.to_dict()), 200


@items_bp.patch("/<int:item_id>")
@token_required
def patch_item(item_id):
    item = _get_owned_item(item_id)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        from .errors import ValidationError

        raise ValidationError("Request body must be a JSON object")

    changes = {}
    if "name" in data:
        from .validation import require_string

        item.name = require_string(data, "name", min_length=1, max_length=120)
        changes["name"] = item.name
    if "description" in data:
        from .validation import require_string

        item.description = require_string(
            data, "description", min_length=0, max_length=5000, required=False
        )
        changes["description"] = item.description

    db.session.flush()
    log_action(g.current_user.id, "update", "item", item.id, changes)
    db.session.commit()
    return jsonify(item.to_dict()), 200


@items_bp.delete("/<int:item_id>")
@token_required
def delete_item(item_id):
    item = _get_owned_item(item_id)
    db.session.delete(item)
    db.session.flush()
    log_action(
        g.current_user.id, "delete", "item", item.id, {"name": item.name}
    )
    db.session.commit()
    return jsonify({"message": "Item deleted"}), 200


def _get_owned_item(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=g.current_user.id).first()
    if item is None:
        raise NotFoundError("Item not found")
    return item
