from flask import request


def get_pagination_params(default_per_page=10, max_per_page=100):
    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(request.args.get("per_page", default_per_page))
    except (TypeError, ValueError):
        per_page = default_per_page

    page = max(page, 1)
    per_page = min(max(per_page, 1), max_per_page)
    return page, per_page


def paginated_response(items, total, page, per_page, key="items"):
    pages = (total + per_page - 1) // per_page if per_page else 0
    return {
        key: items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
        },
    }
