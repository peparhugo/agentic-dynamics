"""Pagination helper producing a consistent envelope with navigation metadata."""
from flask import current_app, request, url_for

from app.schemas import PaginationQuerySchema


def paginate(query, endpoint: str, **url_kwargs):
    """Paginate a SQLAlchemy query using ?page= and ?per_page= query params.

    Returns a dict with `data` and `meta` (including next/prev links).
    Raises marshmallow.ValidationError on bad query params (handled globally).
    """
    params = PaginationQuerySchema().load(
        {k: v for k, v in request.args.items() if k in ("page", "per_page")}
    )
    default_per_page = current_app.config["PAGINATION_DEFAULT_PER_PAGE"]
    max_per_page = current_app.config["PAGINATION_MAX_PER_PAGE"]

    page = params["page"]
    per_page = min(params["per_page"] or default_per_page, max_per_page)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    def page_url(page_num):
        return url_for(endpoint, page=page_num, per_page=per_page, _external=False, **url_kwargs)

    return {
        "data": [item.to_dict() for item in pagination.items],
        "meta": {
            "page": page,
            "per_page": per_page,
            "total_items": pagination.total,
            "total_pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
            "next": page_url(page + 1) if pagination.has_next else None,
            "prev": page_url(page - 1) if pagination.has_prev else None,
        },
    }
