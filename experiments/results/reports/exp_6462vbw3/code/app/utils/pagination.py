import math
from flask import request as flask_request


def paginate(query, page: int = 1, per_page: int = 20, schema_func=None):
    total = query.count()
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    data = [schema_func(item) if schema_func else item.to_dict() for item in items]

    prev_url = None
    next_url = None
    try:
        if page > 1:
            prev_url = f"{flask_request.base_url}?page={page - 1}&per_page={per_page}"
        if page < total_pages:
            next_url = f"{flask_request.base_url}?page={page + 1}&per_page={per_page}"
    except RuntimeError:
        pass

    return {
        "data": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_url": prev_url,
            "next_url": next_url,
        },
    }
