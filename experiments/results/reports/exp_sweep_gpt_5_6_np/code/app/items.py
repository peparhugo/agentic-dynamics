from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from .extensions import db
from .models import AuditLog, Item
from .validation import json_body, pagination_args, validate_item


items_bp = Blueprint("items", __name__, url_prefix="/v1/items")


def current_user_id():
    return int(get_jwt_identity())


def owned_item_or_404(item_id):
    item = db.session.scalar(
        db.select(Item).where(Item.id == item_id, Item.owner_id == current_user_id())
    )
    if item is None:
        return None
    return item


def audit(action, item, details=None):
    db.session.add(
        AuditLog(
            user_id=current_user_id(),
            action=action,
            resource_type="item",
            resource_id=str(item.id),
            ip_address=request.remote_addr or "unknown",
            details=details,
        )
    )


@items_bp.get("")
@items_bp.get("/")
@jwt_required()
def list_items():
    page, per_page = pagination_args()
    query = (
        db.select(Item)
        .where(Item.owner_id == current_user_id())
        .order_by(Item.id.asc())
    )
    result = db.paginate(query, page=page, per_page=per_page, error_out=False)
    return jsonify(
        items=[item.to_dict() for item in result.items],
        pagination={
            "page": result.page,
            "per_page": result.per_page,
            "total": result.total,
            "pages": result.pages,
            "has_next": result.has_next,
            "has_prev": result.has_prev,
        },
    )


@items_bp.post("")
@items_bp.post("/")
@jwt_required()
def create_item():
    values = validate_item(json_body())
    item = Item(owner_id=current_user_id(), **values)
    db.session.add(item)
    db.session.flush()
    audit("create", item, {"name": item.name})
    db.session.commit()
    return jsonify(item=item.to_dict()), 201


@items_bp.get("/<int:item_id>")
@jwt_required()
def get_item(item_id):
    item = owned_item_or_404(item_id)
    if item is None:
        return jsonify(error={"code": "not_found", "message": "Item not found"}), 404
    return jsonify(item=item.to_dict())


@items_bp.patch("/<int:item_id>")
@items_bp.put("/<int:item_id>")
@jwt_required()
def update_item(item_id):
    item = owned_item_or_404(item_id)
    if item is None:
        return jsonify(error={"code": "not_found", "message": "Item not found"}), 404
    values = validate_item(json_body(), partial=request.method == "PATCH")
    for key, value in values.items():
        setattr(item, key, value)
    audit("update", item, {"fields": sorted(values)})
    db.session.commit()
    return jsonify(item=item.to_dict())


@items_bp.delete("/<int:item_id>")
@jwt_required()
def delete_item(item_id):
    item = owned_item_or_404(item_id)
    if item is None:
        return jsonify(error={"code": "not_found", "message": "Item not found"}), 404
    audit("delete", item, {"name": item.name})
    db.session.delete(item)
    db.session.commit()
    return "", 204
