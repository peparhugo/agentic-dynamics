from flask import Blueprint, request, jsonify, current_app, g
from .auth import create_token, jwt_required, rate_limit
from .errors import APIError
import math

api_bp = Blueprint("api", __name__)

# Minimal in-memory "items" dataset
_ITEMS = [
    {"id": i, "name": f"item-{i}", "value": i * 10} for i in range(1, 101)
]

def _get_pagination_params():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10))
    except ValueError:
        raise APIError("page_and_per_page_must_be_integers", 400)
    if page <= 0 or per_page <= 0 or per_page > 100:
        raise APIError("invalid_pagination_values", 400)
    return page, per_page

@api_bp.route("/auth/login", methods=["POST"]) 
def login():
    data = request.get_json(force=True, silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        raise APIError("username_and_password_required", 400)
    # Demo authentication: single user
    if username != "alice" or password != "password123":
        raise APIError("invalid_credentials", 401)
    token = create_token(username)
    return jsonify({"access_token": token})


@api_bp.route("/items", methods=["GET"])
@jwt_required
@rate_limit(lambda: (g.current_user or request.remote_addr))
def list_items():
    page, per_page = _get_pagination_params()
    start = (page - 1) * per_page
    end = start + per_page
    total = len(_ITEMS)
    items = _ITEMS[start:end]
    return jsonify({
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": math.ceil(total / per_page),
    })
