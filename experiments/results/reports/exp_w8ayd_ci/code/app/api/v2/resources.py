from flask import Blueprint, request, jsonify

from app.auth.jwt import jwt_required, requires_role
from app.middleware.validation import validate_request
from app.middleware.rate_limit import dynamic_rate_limit
from app.middleware.audit import audit_request
from app.utils.pagination import parse_pagination_params, paginate_response
from app.utils.serialization import item_create_schema, item_update_schema
from app.utils.errors import NotFoundError

api_v2_bp = Blueprint("api_v2", __name__, url_prefix="/api/v2")

_items_store = {}
_next_id = 1


def _serialize_item(item):
    return {
        "id": item["id"],
        "name": item["name"],
        "description": item["description"],
        "price": item["price"],
        "price_usd": round(item["price"] * 0.85, 2),
        "currency": "USD",
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }


@api_v2_bp.route("/items", methods=["GET"])
@jwt_required
@dynamic_rate_limit(limit_per_window=300, window_seconds=60)
@audit_request
def list_items():
    page, per_page = parse_pagination_params()

    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    all_items = list(_items_store.values())

    reverse = sort_dir == "desc"
    if sort_by in ("id", "name", "price"):
        all_items.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)
    else:
        all_items.sort(key=lambda x: x["id"])

    total = len(all_items)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = [_serialize_item(i) for i in all_items[start:end]]

    result = paginate_response(
        page_items, total, page, per_page, "api_v2.list_items",
        sort_by=sort_by, sort_dir=sort_dir,
    )
    return jsonify({"api_version": "v2", **result}), 200


@api_v2_bp.route("/items/<int:item_id>", methods=["GET"])
@jwt_required
@dynamic_rate_limit(limit_per_window=300, window_seconds=60)
@audit_request
def get_item(item_id):
    item = _items_store.get(item_id)
    if item is None:
        raise NotFoundError(message=f"Item with id {item_id} not found")
    return jsonify({"api_version": "v2", "data": _serialize_item(item)}), 200


@api_v2_bp.route("/items", methods=["POST"])
@jwt_required
@requires_role("admin")
@validate_request(item_create_schema)
@dynamic_rate_limit(limit_per_window=100, window_seconds=60)
@audit_request
def create_item():
    global _next_id
    import time
    data = request.validated_data
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    item = {
        "id": _next_id,
        "name": data["name"],
        "description": data.get("description", ""),
        "price": data["price"],
        "created_at": now,
        "updated_at": now,
    }
    _items_store[_next_id] = item
    _next_id += 1
    return jsonify({"api_version": "v2", "data": _serialize_item(item)}), 201


@api_v2_bp.route("/items/<int:item_id>", methods=["PUT"])
@jwt_required
@requires_role("admin")
@validate_request(item_update_schema, partial=True)
@dynamic_rate_limit(limit_per_window=100, window_seconds=60)
@audit_request
def update_item(item_id):
    import time
    item = _items_store.get(item_id)
    if item is None:
        raise NotFoundError(message=f"Item with id {item_id} not found")

    data = request.validated_data
    for key in ("name", "description", "price"):
        if key in data:
            item[key] = data[key]
    item["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    return jsonify({"api_version": "v2", "data": _serialize_item(item)}), 200


@api_v2_bp.route("/items/<int:item_id>", methods=["DELETE"])
@jwt_required
@requires_role("admin")
@dynamic_rate_limit(limit_per_window=50, window_seconds=60)
@audit_request
def delete_item(item_id):
    if item_id not in _items_store:
        raise NotFoundError(message=f"Item with id {item_id} not found")
    del _items_store[item_id]
    return jsonify({"api_version": "v2", "data": {"deleted": True}}), 200
