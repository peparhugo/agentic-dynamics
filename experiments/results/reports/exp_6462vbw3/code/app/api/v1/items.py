from flask import Blueprint, request, g
from app.extensions import db, limiter
from app.models.item import Item
from app.api.v1.schemas import ItemSchema, ItemUpdateSchema, PaginationSchema
from app.middleware.auth import login_required
from app.middleware.validation import validate_json, validate_query
from app.services.audit import log_audit
from app.utils.pagination import paginate

items_bp = Blueprint("items_v1", __name__, url_prefix="/api/v1/items")


@items_bp.route("", methods=["GET"])
@login_required
@validate_query(PaginationSchema())
def list_items():
    args = request.validated_query
    query = Item.query.filter_by(owner_id=g.current_user.id).order_by(Item.created_at.desc())
    result = paginate(query, page=args["page"], per_page=args["per_page"])
    return result, 200


@items_bp.route("", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
@validate_json(ItemSchema())
def create_item():
    data = request.validated_data
    item = Item(name=data["name"], description=data.get("description"), owner_id=g.current_user.id)
    db.session.add(item)
    db.session.commit()
    log_audit("create", "item", item.id, f"Item '{item.name}' created")
    return item.to_dict(), 201


@items_bp.route("/<int:item_id>", methods=["GET"])
@login_required
def get_item(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=g.current_user.id).first()
    if item is None:
        return {"error": "Item not found"}, 404
    log_audit("read", "item", item.id)
    return item.to_dict(), 200


@items_bp.route("/<int:item_id>", methods=["PUT"])
@login_required
@validate_json(ItemUpdateSchema())
def update_item(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=g.current_user.id).first()
    if item is None:
        return {"error": "Item not found"}, 404

    data = request.validated_data
    if "name" in data:
        item.name = data["name"]
    if "description" in data:
        item.description = data["description"]
    db.session.commit()
    log_audit("update", "item", item.id, f"Item '{item.name}' updated")
    return item.to_dict(), 200


@items_bp.route("/<int:item_id>", methods=["DELETE"])
@login_required
def delete_item(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=g.current_user.id).first()
    if item is None:
        return {"error": "Item not found"}, 404

    db.session.delete(item)
    db.session.commit()
    log_audit("delete", "item", item_id)
    return {"message": "Item deleted"}, 200
