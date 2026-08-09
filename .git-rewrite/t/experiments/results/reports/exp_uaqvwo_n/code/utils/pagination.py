from flask import request

from config import ITEMS_PER_PAGE, MAX_PER_PAGE


def paginate(items, schema=None):
    try:
        page = int(request.args.get("page", 1))
    except (ValueError, TypeError):
        page = 1
    try:
        per_page = int(request.args.get("per_page", ITEMS_PER_PAGE))
    except (ValueError, TypeError):
        per_page = ITEMS_PER_PAGE

    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 1
    if per_page > MAX_PER_PAGE:
        per_page = MAX_PER_PAGE

    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)

    start = (page - 1) * per_page
    end = start + per_page
    page_items = items[start:end]

    data = [item.to_dict() for item in page_items] if not schema else schema.dump(page_items, many=True)

    return {
        "data": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }
