from flask import request, url_for, current_app


def paginate_query(query, schema=None):
    page = request.args.get("page", type=int)
    per_page = request.args.get("per_page", type=int)

    if page is None:
        page = current_app.config.get("PAGINATION_DEFAULT_PAGE", 1)
    if per_page is None:
        per_page = current_app.config.get("PAGINATION_DEFAULT_PER_PAGE", 20)

    max_per_page = current_app.config.get("PAGINATION_MAX_PER_PAGE", 100)
    if per_page > max_per_page:
        per_page = max_per_page
    if page < 1:
        page = 1

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return {
        "data": [item.to_dict() for item in paginated.items],
        "pagination": {
            "page": paginated.page,
            "per_page": paginated.per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "has_next": paginated.has_next,
            "has_prev": paginated.has_prev,
        },
    }
