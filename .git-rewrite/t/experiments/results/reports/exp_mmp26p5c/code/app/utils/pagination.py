from flask import request, current_app


def paginate(query, schema=None):
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", current_app.config.get("PAGINATION_DEFAULT_PER_PAGE", 20), type=int)
    max_per_page = current_app.config.get("PAGINATION_MAX_PER_PAGE", 100)

    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 1
    if per_page > max_per_page:
        per_page = max_per_page

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    items = paginated.items
    if schema:
        items = [schema.dump(item) for item in items]

    return {
        "data": items,
        "pagination": {
            "page": paginated.page,
            "per_page": paginated.per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "has_next": paginated.has_next,
            "has_prev": paginated.has_prev,
            "next_page": paginated.next_num,
            "prev_page": paginated.prev_num,
        },
    }
