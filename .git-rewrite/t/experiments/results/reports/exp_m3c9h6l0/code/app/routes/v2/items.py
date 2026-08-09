from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, current_user
from app.models import db, Item
from app.utils.validators import validate_body, validate_query, ItemCreateSchema, ItemUpdateSchema
from app.utils.pagination import paginate
from app.middleware.audit import audit_action
from marshmallow import Schema, fields


class ItemResponseV2Schema(Schema):
    class Meta:
        fields = ("id", "name", "description", "price", "category", "owner_id", "created_at", "updated_at", "owner_name")


def _enrich_item(item):
    d = ItemResponseV2Schema().dump(item)
    d["owner_name"] = item.owner.username if item.owner else None
    return d


class ItemFilterSchema(Schema):
    category = fields.Str(load_default=None)
    min_price = fields.Float(load_default=None)
    max_price = fields.Float(load_default=None)
    sort_by = fields.Str(load_default="created_at", validate=lambda v: v in ("name", "price", "created_at"))
    order = fields.Str(load_default="desc", validate=lambda v: v in ("asc", "desc"))


v2_bp = Blueprint("v2", __name__, url_prefix="/api/v2")


@v2_bp.route("/items", methods=["GET"])
@jwt_required()
@validate_query(ItemFilterSchema)
def list_items():
    filters = request.validated_query
    query = Item.query.filter_by(owner_id=current_user.id)

    if filters.get("category"):
        query = query.filter(Item.category == filters["category"])
    if filters.get("min_price") is not None:
        query = query.filter(Item.price >= filters["min_price"])
    if filters.get("max_price") is not None:
        query = query.filter(Item.price <= filters["max_price"])

    sort_col = getattr(Item, filters.get("sort_by", "created_at"))
    if filters.get("order") == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    result = paginate(query, schema=ItemResponseV2Schema(), endpoint="v2.list_items")

    result["data"] = [_enrich_item(item) for item in query.paginate(
        page=request.args.get("page", 1, type=int),
        per_page=min(request.args.get("per_page", 20, type=int), 100),
        error_out=False,
    ).items]

    return jsonify(result)


@v2_bp.route("/items/<int:item_id>", methods=["GET"])
@jwt_required()
def get_item(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    return jsonify({"data": _enrich_item(item)})


@v2_bp.route("/items", methods=["POST"])
@jwt_required()
@validate_body(ItemCreateSchema)
@audit_action("item.create", detail="Create a new item (v2)")
def create_item():
    data = request.validated_data
    item = Item(
        name=data["name"],
        description=data.get("description"),
        price=data["price"],
        category=data.get("category"),
        owner_id=current_user.id,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({"data": _enrich_item(item)}), 201


@v2_bp.route("/items/<int:item_id>", methods=["PUT"])
@jwt_required()
@validate_body(ItemUpdateSchema)
@audit_action("item.update", detail="Update an item (v2)")
def update_item(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    data = request.validated_data
    for field in ("name", "description", "price", "category"):
        if field in data and data[field] is not None:
            setattr(item, field, data[field])
    db.session.commit()
    return jsonify({"data": _enrich_item(item)})


@v2_bp.route("/items/<int:item_id>", methods=["DELETE"])
@jwt_required()
@audit_action("item.delete", detail="Delete an item (v2)")
def delete_item(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Item deleted"})
