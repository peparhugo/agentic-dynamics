from flask import request, jsonify, g

from app.api.v1 import bp
from app.api.v1.schemas import ItemCreateSchema, ItemUpdateSchema
from app.middleware.auth import jwt_required
from app.middleware.error_handler import APIError
from app.middleware.logging import audit_log
from app.models.user import (
    create_item,
    get_item,
    get_items_paginated,
    update_item,
    delete_item,
)
from app.utils.pagination import parse_pagination_args


@bp.route("/items", methods=["POST"])
@jwt_required
def create():
    data = ItemCreateSchema().load(request.get_json(silent=True) or {})
    item = create_item(data["name"], data.get("description", ""), g.current_user["id"])

    audit_log("item_created", item_id=item["id"], name=item["name"])

    return jsonify({"item": item}), 201


@bp.route("/items", methods=["GET"])
@jwt_required
def list_items():
    page, per_page = parse_pagination_args()
    result = get_items_paginated(page, per_page)
    return jsonify(result)


@bp.route("/items/<item_id>", methods=["GET"])
@jwt_required
def get_one(item_id):
    item = get_item(item_id)
    if not item:
        raise APIError("Item not found", 404)
    return jsonify({"item": item})


@bp.route("/items/<item_id>", methods=["PUT"])
@jwt_required
def update(item_id):
    item = get_item(item_id)
    if not item:
        raise APIError("Item not found", 404)
    if item["owner_id"] != g.current_user["id"]:
        raise APIError("Forbidden", 403)

    data = ItemUpdateSchema().load(request.get_json(silent=True) or {})
    updated = update_item(item_id, **data)

    audit_log("item_updated", item_id=item_id)

    return jsonify({"item": updated})


@bp.route("/items/<item_id>", methods=["DELETE"])
@jwt_required
def delete(item_id):
    item = get_item(item_id)
    if not item:
        raise APIError("Item not found", 404)
    if item["owner_id"] != g.current_user["id"]:
        raise APIError("Forbidden", 403)

    deleted = delete_item(item_id)

    audit_log("item_deleted", item_id=item_id)

    return jsonify({"item": deleted})
