import re

from flask import current_app, request

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email):
    return bool(email) and bool(EMAIL_RE.match(email))


def get_pagination_args():
    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(
            request.args.get("per_page", current_app.config["DEFAULT_PAGE_SIZE"])
        )
    except (TypeError, ValueError):
        per_page = current_app.config["DEFAULT_PAGE_SIZE"]

    page = max(page, 1)
    per_page = max(1, min(per_page, current_app.config["MAX_PAGE_SIZE"]))
    return page, per_page


def paginated_response(pagination):
    return {
        "items": [item.to_dict() for item in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total_items": pagination.total,
            "total_pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    }
