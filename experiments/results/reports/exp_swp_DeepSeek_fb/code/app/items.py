from flask import Blueprint, g, jsonify, request
from sqlalchemy import select

from .audit import record_audit
from .decorators import token_required
from .errors import ForbiddenError, NotFoundError
from .extensions import db
from .models import Item
from .validators import (
    get_json,
    parse_pagination,
    require_fields,
    validate_description,
    validate_name,
)

items_bp = Blueprint("items", __name__)


def _pagination_body(page, per_page, total, pages, has_next, has_prev, items):
    return {
        "data": [item.to_dict() for item in items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
            "has_next": has_next,
            "has_prev": has_prev,
        },
    }


@items_bp.get("")
@token_required
def list_items():
    page, per_page = parse_pagination()
    stmt = select(Item).order_by(Item.id.desc())
    pagination = db.paginate(
        stmt, page=page, per_page=per_page, error_out=False
    )
    return jsonify(
        _pagination_body(
            pagination.page,
            pagination.per_page,
            pagination.total,
            pagination.pages,
            pagination.has_next,
            pagination.has_prev,
            pagination.items,
        )
    ), 200


@items_bp.post("")
@token_required
def create_item():
    data = get_json()
    require_fields(data, ["name"])
    name = validate_name(data["name"])
    description = validate_description(data.get("description"))

    item = Item(name=name, description=description, owner_id=g.current_user.id)
    db.session.add(item)
    db.session.flush()
    record_audit(
        "item.create", "item", item.id, {"name": name, "description": description}
    )
    db.session.commit()

    return jsonify(item.to_dict()), 201


@items_bp.get("/<int:item_id>")
@token_required
def get_item(item_id):
    item = db.session.get(Item, item_id)
    if item is None:
        raise NotFoundError("Item not found")
    return jsonify(item.to_dict()), 200


@items_bp.put("/<int:item_id>")
@token_required
def update_item(item_id):
    item = db.session.get(Item, item_id)
    if item is None:
        raise NotFoundError("Item not found")
    if item.owner_id != g.current_user.id and g.current_user.role != "admin":
        raise ForbiddenError("You do not own this item")

    data = get_json()
    if "name" in data:
        item.name = validate_name(data["name"])
    if "description" in data:
        item.description = validate_description(data["description"])

    record_audit(
        "item.update",
        "item",
        item.id,
        {"name": item.name, "description": item.description},
    )
    db.session.commit()

    return jsonify(item.to_dict()), 200


@items_bp.delete("/<int:item_id>")
@token_required
def delete_item(item_id):
    item = db.session.get(Item, item_id)
    if item is None:
        raise NotFoundError("Item not found")
    if item.owner_id != g.current_user.id and g.current_user.role != "admin":
        raise ForbiddenError("You do not own this item")

    db.session.delete(item)
    record_audit("item.delete", "item", item_id, {"name": item.name})
    db.session.commit()

    return "", 204
