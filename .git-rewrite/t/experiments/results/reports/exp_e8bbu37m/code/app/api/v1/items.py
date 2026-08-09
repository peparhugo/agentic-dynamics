"""Item resource: authenticated CRUD with validation and pagination."""
from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ...audit import audit
from ...errors import NotFoundError
from ...extensions import db
from ...models import Item
from ...pagination import paginate
from ...schemas import ItemCreateSchema, ItemUpdateSchema
from . import bp

_create_schema = ItemCreateSchema()
_update_schema = ItemUpdateSchema()


def _current_user_id() -> int:
    return int(get_jwt_identity())


def _get_owned_item(item_id: int) -> Item:
    item = db.session.get(Item, item_id)
    if item is None or item.owner_id != _current_user_id():
        # 404 (not 403) so we don't leak existence of others' resources
        raise NotFoundError("Item not found.")
    return item


@bp.get("/items")
@jwt_required()
def list_items():
    query = (
        Item.query.filter_by(owner_id=_current_user_id())
        .order_by(Item.id.asc())
    )
    return jsonify(paginate(query))


@bp.post("/items")
@jwt_required()
def create_item():
    data = _create_schema.load(request.get_json(silent=True) or {})
    user_id = _current_user_id()
    item = Item(owner_id=user_id, **data)
    db.session.add(item)
    db.session.flush()
    audit("item.create", "item", item.id, user_id=user_id)
    db.session.commit()
    return jsonify({"data": item.to_dict()}), 201


@bp.get("/items/<int:item_id>")
@jwt_required()
def get_item(item_id):
    item = _get_owned_item(item_id)
    return jsonify({"data": item.to_dict()})


@bp.patch("/items/<int:item_id>")
@jwt_required()
def update_item(item_id):
    item = _get_owned_item(item_id)
    data = _update_schema.load(request.get_json(silent=True) or {})
    for key, value in data.items():
        setattr(item, key, value)
    audit(
        "item.update",
        "item",
        item.id,
        user_id=_current_user_id(),
        detail={"fields": sorted(data.keys())},
    )
    db.session.commit()
    return jsonify({"data": item.to_dict()})


@bp.delete("/items/<int:item_id>")
@jwt_required()
def delete_item(item_id):
    item = _get_owned_item(item_id)
    db.session.delete(item)
    audit("item.delete", "item", item_id, user_id=_current_user_id())
    db.session.commit()
    return "", 204
