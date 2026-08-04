from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from flask_limiter.util import get_remote_address

from .extensions import limiter
from .schemas import ItemCreate, ItemUpdate, PaginationQuery, parse_json, parse_query
from .utils import handle_validation, paginate


v1_bp = Blueprint("v1", __name__)


@v1_bp.post("/auth/login")
def login():
    # Dummy auth: accept any non-empty username/password; in real-life validate from DB
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = (payload.get("password") or "").strip()
    if not username or not password:
        return jsonify({"error": "invalid_credentials", "message": "username and password required"}), 400

    access = create_access_token(identity=username)
    refresh = create_refresh_token(identity=username)
    return jsonify({"access_token": access, "refresh_token": refresh})


@v1_bp.post("/auth/refresh")
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access = create_access_token(identity=identity)
    return jsonify({"access_token": access})


@v1_bp.get("/items")
@jwt_required()
@handle_validation
@limiter.limit("60 per minute")
def list_items():
    query = parse_query(PaginationQuery, request.args.to_dict())
    items = [
        {"id": item_id, **data} for item_id, data in sorted(current_app.items_store.items())
    ]
    data, meta = paginate(items, query.page, query.per_page)
    return jsonify({"data": data, "meta": meta})


@v1_bp.post("/items")
@jwt_required()
@handle_validation
@limiter.limit("20 per minute")
def create_item():
    payload = request.get_json(silent=True) or {}
    data = parse_json(ItemCreate, payload)
    item_id = current_app.next_id
    current_app.next_id += 1
    current_app.items_store[item_id] = data.model_dump()
    return jsonify({"id": item_id, **current_app.items_store[item_id]}), 201


@v1_bp.get("/items/<int:item_id>")
@jwt_required()
@limiter.limit("60 per minute")
def get_item(item_id: int):
    item = current_app.items_store.get(item_id)
    if not item:
        return jsonify({"error": "not_found", "message": "Item not found"}), 404
    return jsonify({"id": item_id, **item})


@v1_bp.put("/items/<int:item_id>")
@v1_bp.patch("/items/<int:item_id>")
@jwt_required()
@handle_validation
def update_item(item_id: int):
    item = current_app.items_store.get(item_id)
    if not item:
        return jsonify({"error": "not_found", "message": "Item not found"}), 404
    payload = request.get_json(silent=True) or {}
    data = parse_json(ItemUpdate, payload)
    updated = {**item, **{k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}}
    current_app.items_store[item_id] = updated
    return jsonify({"id": item_id, **updated})


@v1_bp.delete("/items/<int:item_id>")
@jwt_required()
def delete_item(item_id: int):
    if item_id in current_app.items_store:
        del current_app.items_store[item_id]
        return ("", 204)
    return jsonify({"error": "not_found", "message": "Item not found"}), 404


# An endpoint with a very low limit to test rate limiting deterministically
@v1_bp.get("/limited")
@limiter.limit("2 per minute")
def limited_public():
    return jsonify({"ok": True, "ip": get_remote_address()})
