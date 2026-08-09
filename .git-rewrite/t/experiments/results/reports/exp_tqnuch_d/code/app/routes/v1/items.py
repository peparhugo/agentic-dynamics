from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import ValidationError

from app import db
from app.models import Item, User
from app.validators import ItemCreateSchema, ItemUpdateSchema, PaginationSchema

bp = Blueprint("items", __name__)


def _resolve_pagination():
    schema = PaginationSchema()
    params = {}
    if request.args.get("page"):
        params["page"] = request.args.get("page")
    if request.args.get("per_page"):
        params["per_page"] = request.args.get("per_page")

    try:
        return schema.load(params)
    except ValidationError:
        return {"page": 1, "per_page": 20}


def _build_pagination_meta(paginated, page, per_page):
    return {
        "page": page,
        "per_page": per_page,
        "total": paginated.total,
        "pages": paginated.pages,
        "has_next": paginated.has_next,
        "has_prev": paginated.has_prev,
    }


@bp.route("/items", methods=["GET"])
@jwt_required(optional=True)
def list_items():
    pag = _resolve_pagination()
    page = pag["page"]
    per_page = pag["per_page"]

    owner_id = request.args.get("owner_id", type=int)
    name_filter = request.args.get("name", type=str)

    query = Item.query.order_by(Item.created_at.desc())

    if owner_id is not None:
        query = query.filter_by(owner_id=owner_id)
    if name_filter:
        query = query.filter(Item.name.ilike(f"%{name_filter}%"))

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return (
        jsonify(
            {
                "data": [item.to_dict() for item in paginated.items],
                "pagination": _build_pagination_meta(paginated, page, per_page),
            }
        ),
        200,
    )


@bp.route("/items/<int:item_id>", methods=["GET"])
@jwt_required(optional=True)
def get_item(item_id):
    item = db.session.get(Item, item_id)
    if item is None:
        return jsonify({"error": "Not Found", "message": "Item not found."}), 404

    return jsonify({"data": item.to_dict()}), 200


@bp.route("/items", methods=["POST"])
@jwt_required()
def create_item():
    identity = get_jwt_identity()
    user = db.session.get(User, int(identity))
    if user is None:
        return jsonify({"error": "Unauthorized", "message": "Invalid user."}), 401

    g.user_id = user.id
    g.username = user.username

    schema = ItemCreateSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify({"error": "Validation Error", "messages": err.messages}), 422

    item = Item(
        name=data["name"],
        description=data.get("description"),
        price=data.get("price"),
        owner_id=user.id,
    )
    db.session.add(item)
    db.session.commit()

    return jsonify({"data": item.to_dict()}), 201


@bp.route("/items/<int:item_id>", methods=["PUT"])
@jwt_required()
def update_item(item_id):
    identity = get_jwt_identity()
    user = db.session.get(User, int(identity))
    if user is None:
        return jsonify({"error": "Unauthorized", "message": "Invalid user."}), 401

    g.user_id = user.id
    g.username = user.username

    item = db.session.get(Item, item_id)
    if item is None:
        return jsonify({"error": "Not Found", "message": "Item not found."}), 404

    if item.owner_id != user.id:
        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": "You do not own this item.",
                }
            ),
            403,
        )

    schema = ItemUpdateSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify({"error": "Validation Error", "messages": err.messages}), 422

    if "name" in data:
        item.name = data["name"]
    if "description" in data:
        item.description = data["description"]
    if "price" in data:
        item.price = data["price"]

    db.session.commit()

    return jsonify({"data": item.to_dict()}), 200


@bp.route("/items/<int:item_id>", methods=["DELETE"])
@jwt_required()
def delete_item(item_id):
    identity = get_jwt_identity()
    user = db.session.get(User, int(identity))
    if user is None:
        return jsonify({"error": "Unauthorized", "message": "Invalid user."}), 401

    g.user_id = user.id
    g.username = user.username

    item = db.session.get(Item, item_id)
    if item is None:
        return jsonify({"error": "Not Found", "message": "Item not found."}), 404

    if item.owner_id != user.id:
        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": "You do not own this item.",
                }
            ),
            403,
        )

    db.session.delete(item)
    db.session.commit()

    return jsonify({"message": "Item deleted."}), 200
