from flask import current_app, request

from app.errors import APIError


def paginate(query, schema=None):
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", current_app.config["DEFAULT_PAGE_SIZE"]))
    except (ValueError, TypeError):
        raise APIError("Invalid pagination parameters", 400)

    if page < 1:
        raise APIError("Page must be a positive integer", 400)

    if per_page < 1 or per_page > current_app.config["MAX_PAGE_SIZE"]:
        raise APIError(
            f"per_page must be between 1 and {current_app.config['MAX_PAGE_SIZE']}",
            400,
        )

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    items = paginated.items
    if schema:
        items = [schema.dump(item) for item in items]

    return {
        "items": items,
        "pagination": {
            "page": paginated.page,
            "per_page": paginated.per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "has_prev": paginated.has_prev,
            "has_next": paginated.has_next,
        },
    }
