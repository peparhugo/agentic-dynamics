"""Offset/limit pagination helpers with a stable response envelope."""
from flask import current_app, request, url_for

from .errors import ValidationAPIError


def get_page_args():
    def _int_arg(name, default, minimum, maximum):
        raw = request.args.get(name, default)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ValidationAPIError(f"Query parameter '{name}' must be an integer.")
        if not (minimum <= value <= maximum):
            raise ValidationAPIError(
                f"Query parameter '{name}' must be between {minimum} and {maximum}.")
        return value

    cfg = current_app.config
    page = _int_arg("page", 1, 1, 1_000_000)
    per_page = _int_arg("per_page", cfg["PAGINATION_DEFAULT_PER_PAGE"],
                        1, cfg["PAGINATION_MAX_PER_PAGE"])
    return page, per_page


def paginated_response(items, page, per_page, total, endpoint, **url_kwargs):
    pages = max(1, -(-total // per_page))  # ceil division

    def _link(p):
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
            "self": _link(page),
            "next": _link(page + 1) if page < pages else None,
            "prev": _link(page - 1) if page > 1 else None,
        },
    }
