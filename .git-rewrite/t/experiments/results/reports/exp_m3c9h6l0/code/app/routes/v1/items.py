from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, current_user
from app.models import db, Item
from app.utils.validators import validate_body, validate_query, ItemCreateSchema, ItemUpdateSchema
from app.utils.pagination import paginate
from app.middleware.audit import audit_action
from marshmallow import Schema, fields


class ItemResponseSchema(Schema):
    class Meta:
        fields = ("id", "name", "description", "price", "category", "owner_id", "created_at", "updated_at")


v1_bp = Blueprint("v1", __name__, url_prefix="/api/v1")


@v1_bp.route("/items", methods=["GET"])
@jwt_required()
def list_items():
    query = Item.query.filter_by(owner_id=current_user.id).order_by(Item.created_at.desc())
    return jsonify(paginate(query, schema=ItemResponseSchema(), endpoint="v1.list_items"))


@v1_bp.route("/items/<int:item_id>", methods=["GET"])
@jwt_required()
def get_item(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    return jsonify({"data": ItemResponseSchema().dump(item)})


@v1_bp.route("/items", methods=["POST"])
@jwt_required()
@validate_body(ItemCreateSchema)
@audit_action("item.create", detail="Create a new item")
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
    return jsonify({"data": ItemResponseSchema().dump(item)}), 201


@v1_bp.route("/items/<int:item_id>", methods=["PUT"])
@jwt_required()
@validate_body(ItemUpdateSchema)
@audit_action("item.update", detail="Update an item")
def update_item(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    data = request.validated_data
    for field in ("name", "description", "price", "category"):
        if field in data and data[field] is not None:
            setattr(item, field, data[field])
    db.session.commit()
    return jsonify({"data": ItemResponseSchema().dump(item)})


@v1_bp.route("/items/<int:item_id>", methods=["DELETE"])
@jwt_required()
@audit_action("item.delete", detail="Delete an item")
def delete_item(item_id):
    item = Item.query.filter_by(id=item_id, owner_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Item deleted"})
