from flask import request, url_for

from app.config import Config


def paginate(items_fn, sort_by="id", order="asc"):

    page = request.args.get("page", Config.PAGINATION_DEFAULT_PAGE, type=int)
    per_page = request.args.get(
        "per_page", Config.PAGINATION_DEFAULT_PER_PAGE, type=int
    )
    if per_page > Config.PAGINATION_MAX_PER_PAGE:
        per_page = Config.PAGINATION_MAX_PER_PAGE
    if page < 1:
        page = 1

    items, total = items_fn(page=page, per_page=per_page, sort_by=sort_by, order=order)
    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0

    base_url = request.base_url
    links = {}

    if page > 1:
        links["prev"] = f"{base_url}?page={page - 1}&per_page={per_page}"
    if page < total_pages:
        links["next"] = f"{base_url}?page={page + 1}&per_page={per_page}"
    links["first"] = f"{base_url}?page=1&per_page={per_page}"
    links["last"] = f"{base_url}?page={total_pages}&per_page={per_page}"

    return {
        "items": [item.to_dict() for item in items],
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
        "links": links,
    }
