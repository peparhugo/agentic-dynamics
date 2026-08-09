from flask import request, jsonify
from marshmallow import ValidationError
from app.config import Config
from app.schemas import PaginationSchema


def paginate(query, schema=None):
    if schema is None:
        schema = PaginationSchema()
    try:
        params = schema.load(request.args.to_dict())
    except ValidationError as e:
        return jsonify({"error": "Invalid pagination parameters", "details": e.messages}), 400

    page = params["page"]
    per_page = params["per_page"]
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        "data": [item.to_dict() for item in items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": max(1, (total + per_page - 1) // per_page),
            "has_next": page * per_page < total,
            "has_prev": page > 1,
        },
    })
