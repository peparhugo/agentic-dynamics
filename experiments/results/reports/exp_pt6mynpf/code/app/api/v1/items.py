"""Item CRUD endpoints (authenticated, owner-scoped)."""
from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.api.v1 import api_v1
from app.audit import audit
from app.errors import APIError
from app.extensions import db
from app.models import Item
from app.pagination import paginate
from app.schemas import ItemCreateSchema, ItemUpdateSchema


def _json_body() -> dict:
    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        raise APIError("Request body must be a JSON object.", 400)
    return data


def _current_user_id() -> int:
    return int(get_jwt_identity())


def _get_owned_item(item_id: int) -> Item:
    item = db.session.get(Item, item_id)
    if item is None:
        raise APIError("Item not found.", 404)
    if item.owner_id != _current_user_id():
        # Owner-scoped API: hide other users' resources.
        raise APIError("Item not found.", 404)
    return item


@api_v1.get("/items")
@jwt_required()
def list_items():
    query = Item.query.filter_by(owner_id=_current_user_id()).order_by(Item.id)
    return paginate(query, "api_v1.list_items")


@api_v1.post("/items")
@jwt_required()
def create_item():
    data = ItemCreateSchema().load(_json_body())
    item = Item(
        name=data["name"],
        description=data.get("description"),
        price=data["price"],
        owner_id=_current_user_id(),
    )
    db.session.add(item)
    db.session.commit()

    audit("item.create", user_id=item.owner_id, resource_type="item", resource_id=item.id, status_code=201)
    return {"data": item.to_dict()}, 201


@api_v1.get("/items/<int:item_id>")
@jwt_required()
def get_item(item_id: int):
    item = _get_owned_item(item_id)
    return {"data": item.to_dict()}


@api_v1.patch("/items/<int:item_id>")
@jwt_required()
def update_item(item_id: int):
    item = _get_owned_item(item_id)
    data = ItemUpdateSchema().load(_json_body())
    if not data:
        raise APIError("At least one updatable field must be provided.", 400)

    for field, value in data.items():
        setattr(item, field, value)
    db.session.commit()

    audit(
        "item.update",
        user_id=item.owner_id,
        resource_type="item",
        resource_id=item.id,
        status_code=200,
        detail=f"fields={sorted(data.keys())}",
    )
    return {"data": item.to_dict()}


@api_v1.delete("/items/<int:item_id>")
@jwt_required()
def delete_item(item_id: int):
    item = _get_owned_item(item_id)
    db.session.delete(item)
    db.session.commit()

    audit("item.delete", user_id=_current_user_id(), resource_type="item", resource_id=item_id, status_code=204)
    return "", 204
