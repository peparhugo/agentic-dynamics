from flask import g, jsonify, request

from app import db
from app.auth import login_required
from app.errors import APIError
from app.middleware import log_audit
from app.models import Item
from app.pagination import paginate
from app.validators import ItemSchema, validate_request

from . import bp


@bp.route("/items", methods=["GET"])
@login_required
def list_items():
    query = Item.query.order_by(Item.created_at.desc())
    result = paginate(query)
    result["items"] = [item.to_dict() for item in result["items"]]
    return jsonify(result), 200


@bp.route("/items", methods=["POST"])
@login_required
def create_item():
    data = validate_request(ItemSchema(), request.get_json(silent=True) or {})

    item = Item(
        name=data["name"],
        description=data.get("description"),
        owner_id=g.current_user.id,
    )
    db.session.add(item)
    db.session.commit()

    log_audit(
        user_id=g.current_user.id,
        action="create",
        resource="item",
        resource_id=item.id,
        details=f"Created item: {item.name}",
        request=request,
    )

    return jsonify(item.to_dict()), 201


@bp.route("/items/<int:item_id>", methods=["GET"])
@login_required
def get_item(item_id):
    item = Item.query.get(item_id)
    if not item:
        raise APIError("Item not found", 404)
    return jsonify(item.to_dict()), 200


@bp.route("/items/<int:item_id>", methods=["PUT"])
@login_required
def update_item(item_id):
    item = Item.query.get(item_id)
    if not item:
        raise APIError("Item not found", 404)

    if item.owner_id != g.current_user.id:
        raise APIError("You do not have permission to modify this item", 403)

    data = validate_request(ItemSchema(), request.get_json(silent=True) or {})

    item.name = data["name"]
    item.description = data.get("description")
    db.session.commit()

    log_audit(
        user_id=g.current_user.id,
        action="update",
        resource="item",
        resource_id=item.id,
        details=f"Updated item: {item.name}",
        request=request,
    )

    return jsonify(item.to_dict()), 200


@bp.route("/items/<int:item_id>", methods=["DELETE"])
@login_required
def delete_item(item_id):
    item = Item.query.get(item_id)
    if not item:
        raise APIError("Item not found", 404)

    if item.owner_id != g.current_user.id:
        raise APIError("You do not have permission to delete this item", 403)

    log_audit(
        user_id=g.current_user.id,
        action="delete",
        resource="item",
        resource_id=item.id,
        details=f"Deleted item: {item.name}",
        request=request,
    )

    db.session.delete(item)
    db.session.commit()

    return jsonify({"message": "Item deleted"}), 200
