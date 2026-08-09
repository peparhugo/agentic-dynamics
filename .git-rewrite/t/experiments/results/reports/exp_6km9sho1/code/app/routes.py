from flask import Blueprint, request, jsonify
import time
from flask_jwt_extended import jwt_required, create_access_token
from .schemas import LoginSchema, ItemQuerySchema
from .models import ITEMS, User
from .audit import log_request

api = Blueprint("api_v1", __name__)

@api.after_request
def after_request_logging(response):
    # Simple audit log per request
    try:
        ip = request.remote_addr or ""  # client IP
        path = request.path
        status = response.status_code
        method = request.method
        user = None
        if request.headers.get("Authorization"):
            # crude extraction; token is after Bearer
            token = request.headers.get("Authorization").split()[1]
            user = token[:10] if token else None
        entry = f"{ip} {method} {path} -> {status} user={user}"
        # If app context is available, use its logger; else print
        if request.app and hasattr(request.app, 'audit_logger'):
            request.app.audit_logger.info(entry)
        else:
            print(entry)
    except Exception:
        pass
    return response

@api.route("/v1/auth/login", methods=["POST"])
def login():
    # Validate input
    json_data = request.get_json(force=True) or {}
    schema = LoginSchema()
    errors = schema.validate(json_data)
    if errors:
        return jsonify({"errors": errors}), 400
    username = json_data.get("username")
    password = json_data.get("password")
    user = User.get(username)
    if not user or user.password != password:
        return jsonify({"msg": "Bad username or password"}), 401
    access_token = create_access_token(identity=username)
    return jsonify({"access_token": access_token})

@api.route("/v1/items", methods=["GET"])
@jwt_required()
def get_items():
    # Pagination inputs
    q = request.args
    schema = ItemQuerySchema()
    errors = schema.validate(q)
    if errors:
        return jsonify({"errors": errors}), 400
    page = int(q.get("page", 1))
    per_page = int(q.get("per_page", 5))
    # Simple in-memory pagination
    start = (page - 1) * per_page
    end = start + per_page
    data_slice = ITEMS[start:end]
    total = len(ITEMS)
    return jsonify({
        "page": page,
        "per_page": per_page,
        "total": total,
        "items": data_slice,
    })

@api.route("/v1/public", methods=["GET"])
def public_endpoint():
    return jsonify({"msg": "Public endpoint - no auth required"})
