import re

from flask import current_app, request

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email):
    return bool(email) and bool(EMAIL_RE.match(email))


def get_pagination_params():
    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(request.args.get("per_page", current_app.config["PAGINATION_DEFAULT_PAGE_SIZE"]))
    except (TypeError, ValueError):
        per_page = current_app.config["PAGINATION_DEFAULT_PAGE_SIZE"]

    page = max(page, 1)
    max_page_size = current_app.config["PAGINATION_MAX_PAGE_SIZE"]
    per_page = min(max(per_page, 1), max_page_size)
    return page, per_page


def paginated_response(query, page, per_page, serializer):
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page if total else 0
    return {
        "items": [serializer(item) for item in items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_items": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }
