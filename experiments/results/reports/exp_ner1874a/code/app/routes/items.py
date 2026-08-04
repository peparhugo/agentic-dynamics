from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import Schema, fields, validate, ValidationError

from ..extensions import limiter

bp = Blueprint("items", __name__)


# In-memory storage for demo purposes
@dataclass
class Item:
    id: int
    name: str
    description: str | None = None


_ITEMS: dict[int, Item] = {}
_NEXT_ID = 1


class ItemCreateSchema(Schema):
    name = fields.String(required=True, validate=[validate.Length(min=1, max=100)])
    description = fields.String(load_default=None, allow_none=True, validate=[validate.Length(max=500)])


class ItemUpdateSchema(Schema):
    name = fields.String(load_default=None, allow_none=True, validate=[validate.Length(min=1, max=100)])
    description = fields.String(load_default=None, allow_none=True, validate=[validate.Length(max=500)])


class ItemOutSchema(Schema):
    id = fields.Integer(required=True)
    name = fields.String(required=True)
    description = fields.String(allow_none=True)


item_create_schema = ItemCreateSchema()
item_update_schema = ItemUpdateSchema()
item_out_schema = ItemOutSchema()


def _paginate(items: list[dict[str, Any]], page: int, per_page: int) -> dict[str, Any]:
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "items": items[start:end],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": (total + per_page - 1) // per_page,
    }


@bp.get("")
@jwt_required()
@limiter.limit("100 per minute")
def list_items():
    # Pagination params
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10))
        if page < 1 or per_page < 1 or per_page > 100:
            raise ValueError
    except ValueError:
        return jsonify({"error": {"type": "ValidationError", "message": "Invalid pagination parameters"}}), 422

    items = [asdict(i) for i in _ITEMS.values()]
    items.sort(key=lambda x: x["id"])  # consistent order
    return jsonify(_paginate(items, page, per_page))


@bp.post("")
@jwt_required()
@limiter.limit("50 per minute")
def create_item():
    try:
        payload = item_create_schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify({"error": {"type": "ValidationError", "message": err.messages}}), 422

    global _NEXT_ID
    item = Item(id=_NEXT_ID, **payload)
    _ITEMS[item.id] = item
    _NEXT_ID += 1
    return jsonify(item_out_schema.dump(asdict(item))), 201


@bp.get("/<int:item_id>")
@jwt_required()
@limiter.limit("200 per minute")
def get_item(item_id: int):
    item = _ITEMS.get(item_id)
    if not item:
        return jsonify({"error": {"type": "NotFound", "message": "Item not found"}}), 404
    return jsonify(item_out_schema.dump(asdict(item)))


@bp.put("/<int:item_id>")
@jwt_required()
@limiter.limit("50 per minute")
def update_item(item_id: int):
    try:
        payload = item_update_schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify({"error": {"type": "ValidationError", "message": err.messages}}), 422

    item = _ITEMS.get(item_id)
    if not item:
        return jsonify({"error": {"type": "NotFound", "message": "Item not found"}}), 404

    if payload.get("name") is not None:
        item.name = payload["name"]
    if payload.get("description") is not None:
        item.description = payload["description"]

    return jsonify(item_out_schema.dump(asdict(item)))


@bp.delete("/<int:item_id>")
@jwt_required()
@limiter.limit("30 per minute")
def delete_item(item_id: int):
    item = _ITEMS.pop(item_id, None)
    if not item:
        return jsonify({"error": {"type": "NotFound", "message": "Item not found"}}), 404
    return ("", 204)
