from flask import request, url_for
from werkzeug.exceptions import BadRequest

from app.schemas import PaginationSchema


def paginate(query, schema=None, per_page=None, max_per_page=100, **kwargs):
    page = request.args.get("page", 1, type=int)
    per_page = per_page or request.args.get("per_page", 20, type=int)
    sort_by = request.args.get("sort_by", "created_at")
    sort_order = request.args.get("sort_order", "desc")

    if page < 1:
        raise BadRequest("Page must be a positive integer.")
    if per_page < 1 or per_page > max_per_page:
        raise BadRequest(f"per_page must be between 1 and {max_per_page}.")

    allowed_sort_fields = {"created_at", "updated_at", "id", "name", "price", "status"}
    if sort_by not in allowed_sort_fields:
        sort_by = "created_at"

    order_column = getattr(query.column_descriptions[0]["type"], sort_by, None)
    if order_column is not None:
        if sort_order == "asc":
            query = query.order_by(order_column.asc())
        else:
            query = query.order_by(order_column.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False, **kwargs)

    items = pagination.items
    if schema:
        items = [schema.dump(item) for item in pagination.items]

    result = {
        "data": items,
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    }

    if pagination.has_next:
        result["pagination"]["next_page"] = pagination.page + 1
    if pagination.has_prev:
        result["pagination"]["prev_page"] = pagination.page - 1

    return result


def build_meta_response(data, message=None, status_code=200, meta=None):
    response = {"data": data}
    if message:
        response["message"] = message
    if meta:
        response["meta"] = meta
    return response, status_code
