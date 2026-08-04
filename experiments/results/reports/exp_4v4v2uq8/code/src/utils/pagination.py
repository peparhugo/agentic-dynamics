from flask import request, url_for


def paginate(items: list, schema=None):
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    page = max(1, page)
    per_page = max(1, min(per_page, 100))

    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)

    start = (page - 1) * per_page
    end = start + per_page
    page_items = items[start:end]

    if schema:
        page_items = [schema.dump(item) for item in page_items]

    result = {
        "data": page_items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }

    if page < total_pages:
        result["pagination"]["next"] = _build_url(page=page + 1, per_page=per_page)
    if page > 1:
        result["pagination"]["prev"] = _build_url(page=page - 1, per_page=per_page)

    return result


def _build_url(**kwargs):
    args = request.args.to_dict()
    args.update({k: v for k, v in kwargs.items()})
    return url_for(request.endpoint, **args, _external=False)
