"""Offset/limit pagination helpers for SQL-backed list endpoints."""
import math

from flask import current_app, request, url_for

from .errors import ValidationError


def page_args():
    """Parse and validate ?page= and ?per_page= query params."""
    cfg = current_app.config
    default_per = cfg["PAGINATION_DEFAULT_PER_PAGE"]
    max_per = cfg["PAGINATION_MAX_PER_PAGE"]

    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", default_per))
    except (TypeError, ValueError):
        raise ValidationError("page and per_page must be integers")

    if page < 1:
        raise ValidationError("page must be >= 1")
    if per_page < 1 or per_page > max_per:
        raise ValidationError(f"per_page must be between 1 and {max_per}")
    return page, per_page


def paginated_response(items, total, page, per_page, endpoint, **url_kwargs):
    """Build a standard paginated envelope with navigation links."""
    pages = max(1, math.ceil(total / per_page)) if total else 1

    def link(p):
        return url_for(endpoint, page=p, per_page=per_page, **url_kwargs)

    return {
        "data": items,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
        },
        "links": {
            "self": link(page),
            "first": link(1),
            "last": link(pages),
            "next": link(page + 1) if page < pages else None,
            "prev": link(page - 1) if page > 1 else None,
        },
    }
