from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.middleware.auth import login_required
from app.models import AuditLog, Item
from app.validators import ItemCreateSchema, ItemUpdateSchema, validate_schema

bp = Blueprint("items", __name__, url_prefix="/v1")


def paginate(query, page, per_page):
    per_page = min(per_page, 100)
    total = query.count()
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    total_pages = (total + per_page - 1) // per_page if per_page else 0
    return {
        "items": [item.to_dict() for item in items],
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
    }


@bp.route("/items", methods=["GET"])
@login_required
def list_items():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20

    query = Item.query.order_by(Item.created_at.desc())
    result = paginate(query, page, per_page)
    return jsonify(result), 200


@bp.route("/items/<int:item_id>", methods=["GET"])
@login_required
def get_item(item_id):
    item = Item.query.get(item_id)
    if item is None:
        return jsonify({"error": "item not found"}), 404
    return jsonify(item.to_dict()), 200


@bp.route("/items", methods=["POST"])
@login_required
@validate_schema(ItemCreateSchema)
def create_item(validated_data):
    item = Item(
        name=validated_data["name"],
        description=validated_data.get("description"),
        price=validated_data["price"],
        owner_id=g.current_user.id,
    )
    db.session.add(item)
    db.session.commit()

    AuditLog.log(
        user_id=g.current_user.id,
        action="create",
        resource="item",
        resource_id=item.id,
        details=f"Created item '{item.name}'",
        ip_address=request.remote_addr,
    )

    return jsonify(item.to_dict()), 201


@bp.route("/items/<int:item_id>", methods=["PUT"])
@login_required
@validate_schema(ItemUpdateSchema)
def update_item(item_id, validated_data):
    item = Item.query.get(item_id)
    if item is None:
        return jsonify({"error": "item not found"}), 404

    if item.owner_id != g.current_user.id:
        return jsonify({"error": "forbidden"}), 403

    if not validated_data:
        return jsonify({"error": "no fields to update"}), 400

    for key, value in validated_data.items():
        if value is not None:
            setattr(item, key, value)

    db.session.commit()

    AuditLog.log(
        user_id=g.current_user.id,
        action="update",
        resource="item",
        resource_id=item.id,
        details=f"Updated item '{item.name}'",
        ip_address=request.remote_addr,
    )

    return jsonify(item.to_dict()), 200


@bp.route("/items/<int:item_id>", methods=["DELETE"])
@login_required
def delete_item(item_id):
    item = Item.query.get(item_id)
    if item is None:
        return jsonify({"error": "item not found"}), 404

    if item.owner_id != g.current_user.id:
        return jsonify({"error": "forbidden"}), 403

    db.session.delete(item)
    db.session.commit()

    AuditLog.log(
        user_id=g.current_user.id,
        action="delete",
        resource="item",
        resource_id=item_id,
        details=f"Deleted item '{item.name}'",
        ip_address=request.remote_addr,
    )

    return jsonify({"message": "item deleted"}), 200
