from flask import Blueprint, g, jsonify, request

from app import db
from app.audit import log_audit
from app.errors import ForbiddenError, NotFoundError, ValidationError
from app.middleware import jwt_required
from app.models import Item
from app.validators import ItemCreateSchema, ItemUpdateSchema

items_bp = Blueprint("items", __name__)


def _serialize_item(item):
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "owner_id": item.owner_id,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


@items_bp.route("", methods=["POST"])
@jwt_required
def create_item():
    schema = ItemCreateSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except Exception as e:
        raise ValidationError(str(e))

    item = Item(
        name=data["name"],
        description=data.get("description"),
        owner_id=g.current_user_id,
    )
    db.session.add(item)
    db.session.flush()
    log_audit(
        g.current_user_id,
        "CREATE",
        "item",
        item.id,
        details={"name": item.name},
        ip_address=request.remote_addr,
    )
    db.session.commit()

    return jsonify(_serialize_item(item)), 201


@items_bp.route("", methods=["GET"])
@jwt_required
def list_items():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    if page < 1:
        raise ValidationError("page must be >= 1")
    if per_page < 1 or per_page > 100:
        raise ValidationError("per_page must be between 1 and 100")

    pagination = Item.query.order_by(Item.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return (
        jsonify(
            {
                "items": [_serialize_item(item) for item in pagination.items],
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            }
        ),
        200,
    )


@items_bp.route("/<int:item_id>", methods=["GET"])
@jwt_required
def get_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        raise NotFoundError("Item not found")
    return jsonify(_serialize_item(item)), 200


@items_bp.route("/<int:item_id>", methods=["PUT"])
@jwt_required
def update_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        raise NotFoundError("Item not found")
    if item.owner_id != g.current_user_id:
        raise ForbiddenError("You can only update your own items")

    schema = ItemUpdateSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except Exception as e:
        raise ValidationError(str(e))

    if "name" in data and data["name"] is not None:
        item.name = data["name"]
    if "description" in data:
        item.description = data["description"]

    log_audit(
        g.current_user_id,
        "UPDATE",
        "item",
        item.id,
        details={"name": item.name, "description": item.description},
        ip_address=request.remote_addr,
    )
    db.session.commit()

    return jsonify(_serialize_item(item)), 200


@items_bp.route("/<int:item_id>", methods=["DELETE"])
@jwt_required
def delete_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        raise NotFoundError("Item not found")
    if item.owner_id != g.current_user_id:
        raise ForbiddenError("You can only delete your own items")

    db.session.delete(item)
    log_audit(
        g.current_user_id,
        "DELETE",
        "item",
        item_id,
        ip_address=request.remote_addr,
    )
    db.session.commit()

    return "", 204
