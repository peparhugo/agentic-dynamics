from datetime import datetime

from flask import request

from app.errors import APIError


def paginate_args():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10))
    except (TypeError, ValueError):
        raise APIError("page and per_page must be integers", 400)

    if page < 1:
        raise APIError("page must be >= 1", 400)
    if per_page < 1 or per_page > 100:
        raise APIError("per_page must be between 1 and 100", 400)

    return page, per_page


def paginated_response(query, page, per_page, serialize=lambda item: item.to_dict()):
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "items": [serialize(item) for item in pagination.items],
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "total_pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }


def parse_iso_datetime(value, field_name="due_date"):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except ValueError:
            raise APIError(f"{field_name} must be a valid ISO 8601 datetime", 400)
    raise APIError(f"{field_name} must be a valid ISO 8601 datetime string", 400)


def require_fields(data, fields):
    if not isinstance(data, dict):
        raise APIError("Request body must be a JSON object", 400)
    missing = [f for f in fields if not data.get(f)]
    if missing:
        raise APIError(f"Missing required field(s): {', '.join(missing)}", 400)
