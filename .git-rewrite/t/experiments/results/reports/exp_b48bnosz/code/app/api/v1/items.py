"""Item CRUD: authenticated, validated, paginated, audited."""
from flask import jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from ...audit import set_audit_action
from ...errors import ApiError
from ...extensions import db, limiter
from ...models import Item
from ...pagination import paginate
from ...schemas import ItemCreateSchema, ItemUpdateSchema
from . import bp


def _json_body() -> dict:
    if not request.is_json:
        raise ApiError(
            "Request body must be JSON.", status_code=415, code="unsupported_media_type"
        )
    return request.get_json(silent=True) or {}


def _get_owned_item(item_id: int) -> Item:
    item = db.session.get(Item, item_id)
    if item is None:
        raise ApiError("Item not found.", status_code=404, code="not_found")
    user_id = int(get_jwt_identity())
    if item.owner_id != user_id and get_jwt().get("role") != "admin":
        raise ApiError("You do not own this item.", status_code=403, code="forbidden")
    return item


@bp.get("/items")
@jwt_required()
@limiter.limit("60 per minute")
def list_items():
    query = Item.query.order_by(Item.id)
    owner_id = request.args.get("owner_id", type=int)
    if owner_id is not None:
        query = query.filter_by(owner_id=owner_id)
    return jsonify(paginate(query))


@bp.get("/items/<int:item_id>")
@jwt_required()
def get_item(item_id: int):
    item = db.session.get(Item, item_id)
    if item is None:
        raise ApiError("Item not found.", status_code=404, code="not_found")
    return jsonify({"data": item.to_dict()})


@bp.post("/items")
@jwt_required()
@limiter.limit("30 per minute")
def create_item():
    data = ItemCreateSchema().load(_json_body())
    item = Item(
        name=data["name"],
        description=data["description"],
        price=data["price"],
        owner_id=int(get_jwt_identity()),
    )
    db.session.add(item)
    db.session.commit()
    set_audit_action("item.create", f"item_id={item.id}")
    return jsonify({"data": item.to_dict()}), 201


@bp.patch("/items/<int:item_id>")
@jwt_required()
def update_item(item_id: int):
    item = _get_owned_item(item_id)
    data = ItemUpdateSchema().load(_json_body())
    if not data:
        raise ApiError("No valid fields to update.", status_code=400, code="empty_update")
    for field, value in data.items():
        setattr(item, field, value)
    db.session.commit()
    set_audit_action("item.update", f"item_id={item.id} fields={sorted(data)}")
    return jsonify({"data": item.to_dict()})


@bp.delete("/items/<int:item_id>")
@jwt_required()
def delete_item(item_id: int):
    item = _get_owned_item(item_id)
    db.session.delete(item)
    db.session.commit()
    set_audit_action("item.delete", f"item_id={item_id}")
    return "", 204
