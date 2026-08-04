from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Dict

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from ..schemas import ItemCreateSchema, ItemUpdateSchema, PaginationQuerySchema
from ..extensions import limiter


bp = Blueprint("items", __name__)


# In-memory store for example. Reset between tests by app factory re-creation.
_id_counter = itertools.count(1)
_ITEMS: Dict[int, dict] = {}


def _paginate(items: list[dict], page: int, page_size: int):
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end]


@bp.get("")
@jwt_required()
def list_items():
    args = PaginationQuerySchema().load(request.args)
    page = args["page"]
    page_size = args["page_size"]
    sorted_items = [dict(id=i, **data) for i, data in sorted(_ITEMS.items(), key=lambda x: x[0])]
    paged = _paginate(sorted_items, page, page_size)
    return {
        "items": paged,
        "page": page,
        "page_size": page_size,
        "total": len(sorted_items),
    }


@bp.post("")
@jwt_required()
@limiter.limit("20 per minute")
def create_item():
    payload = request.get_json(silent=True) or {}
    data = ItemCreateSchema().load(payload)
    item_id = next(_id_counter)
    _ITEMS[item_id] = {"name": data["name"], "description": data.get("description")}
    return {"id": item_id, **_ITEMS[item_id]}, 201


@bp.get("/<int:item_id>")
@jwt_required()
@limiter.limit("60 per minute")
def get_item(item_id: int):
    item = _ITEMS.get(item_id)
    if not item:
        return {"error": {"message": "Item not found"}}, 404
    return {"id": item_id, **item}


@bp.put("/<int:item_id>")
@jwt_required()
@limiter.limit("20 per minute")
def update_item(item_id: int):
    if item_id not in _ITEMS:
        return {"error": {"message": "Item not found"}}, 404
    payload = request.get_json(silent=True) or {}
    data = ItemUpdateSchema().load(payload)
    _ITEMS[item_id].update(data)
    return {"id": item_id, **_ITEMS[item_id]}


@bp.delete("/<int:item_id>")
@jwt_required()
@limiter.limit("10 per minute")
def delete_item(item_id: int):
    if item_id not in _ITEMS:
        return {"error": {"message": "Item not found"}}, 404
    del _ITEMS[item_id]
    return {"status": "deleted"}
