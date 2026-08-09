from flask import request
from flask import current_app


def get_pagination_params():
    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(request.args.get("per_page", current_app.config["DEFAULT_PAGE_SIZE"]))
        max_page_size = current_app.config["MAX_PAGE_SIZE"]
        if per_page < 1:
            per_page = current_app.config["DEFAULT_PAGE_SIZE"]
        if per_page > max_page_size:
            per_page = max_page_size
    except (ValueError, TypeError):
        per_page = current_app.config["DEFAULT_PAGE_SIZE"]

    return page, per_page


def paginate_query(query, schema=None):
    page, per_page = get_pagination_params()
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    result = {
        "data": [item.to_dict() for item in paginated.items],
        "meta": {
            "page": paginated.page,
            "per_page": paginated.per_page,
            "total": paginated.total,
            "total_pages": paginated.pages,
        },
    }
    return result, 200
