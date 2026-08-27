from flask import Blueprint, g, jsonify

from .audit import log_audit
from .decorators import token_required
from .errors import APIError
from .extensions import db
from .models import Item
from .validators import get_json, get_pagination, optional_number, require_string

items_bp = Blueprint("items", __name__)


@items_bp.route("", methods=["GET"])
@token_required
def list_items():
    page, per_page = get_pagination()
    query = Item.query
    total = query.count()
    items = query.order_by(Item.id.asc()).offset((page - 1) * per_page).limit(per_page).all()
    pages = (total + per_page - 1) // per_page
    return jsonify(
        {
            "data": [item.to_dict() for item in items],
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
        }
    ), 200


@items_bp.route("", methods=["POST"])
@token_required
def create_item():
    data = get_json()
    name = require_string(data, "name", min_length=1, max_length=120)
    description = require_string(data, "description", required=False, max_length=500)
    price = optional_number(data, "price")
    if price is not None and price < 0:
        raise APIError("Field 'price' must be >= 0", 400, "invalid_value")

    item = Item(name=name, description=description, price=price, created_by=g.current_user.id)
    db.session.add(item)
    db.session.flush()
    log_audit("create", "item", resource_id=item.id, user_id=g.current_user.id)
    db.session.commit()

    return jsonify(item.to_dict()), 201


@items_bp.route("/<int:item_id>", methods=["GET"])
@token_required
def get_item(item_id):
    item = db.session.get(Item, item_id)
    if item is None:
        raise APIError("Item not found", 404, "not_found")
    return jsonify(item.to_dict()), 200


@items_bp.route("/<int:item_id>", methods=["PUT"])
@token_required
def update_item(item_id):
    item = db.session.get(Item, item_id)
    if item is None:
        raise APIError("Item not found", 404, "not_found")

    data = get_json()
    name = require_string(data, "name", min_length=1, max_length=120)
    description = require_string(data, "description", required=False, max_length=500)
    price = optional_number(data, "price")
    if price is not None and price < 0:
        raise APIError("Field 'price' must be >= 0", 400, "invalid_value")

    item.name = name
    item.description = description
    item.price = price

    log_audit("update", "item", resource_id=item.id, user_id=g.current_user.id)
    db.session.commit()

    return jsonify(item.to_dict()), 200


@items_bp.route("/<int:item_id>", methods=["PATCH"])
@token_required
def partial_update_item(item_id):
    item = db.session.get(Item, item_id)
    if item is None:
        raise APIError("Item not found", 404, "not_found")

    data = get_json()
    if "name" in data:
        item.name = require_string(data, "name", min_length=1, max_length=120)
    if "description" in data:
        item.description = require_string(data, "description", required=False, max_length=500)
    if "price" in data:
        item.price = optional_number(data, "price")
        if item.price is not None and item.price < 0:
            raise APIError("Field 'price' must be >= 0", 400, "invalid_value")

    log_audit("update", "item", resource_id=item.id, user_id=g.current_user.id)
    db.session.commit()

    return jsonify(item.to_dict()), 200


@items_bp.route("/<int:item_id>", methods=["DELETE"])
@token_required
def delete_item(item_id):
    item = db.session.get(Item, item_id)
    if item is None:
        raise APIError("Item not found", 404, "not_found")

    db.session.delete(item)
    log_audit("delete", "item", resource_id=item.id, user_id=g.current_user.id)
    db.session.commit()

    return "", 204
