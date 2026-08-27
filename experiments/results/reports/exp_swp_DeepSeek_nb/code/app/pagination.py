from flask import current_app

from .validation import validate_pagination


def paginate(query, args):
    page, per_page = validate_pagination(args)
    max_per_page = current_app.config["MAX_PAGE_SIZE"]
    per_page = min(per_page, max_per_page)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "items": [item.to_dict() for item in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    }
