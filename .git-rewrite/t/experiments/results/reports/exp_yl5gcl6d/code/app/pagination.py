"""Pagination helpers for list endpoints."""
from flask import current_app, request, url_for

from .errors import ValidationApiError


def get_page_args() -> tuple[int, int]:
    """Read and validate ?page= and ?per_page= query params."""
    cfg = current_app.config
    errors = {}

    def read_int(name: str, default: int) -> int:
        raw = request.args.get(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            errors[name] = "Must be an integer."
            return default

    page = read_int("page", 1)
    per_page = read_int("per_page", cfg["PAGINATION_DEFAULT_PER_PAGE"])

    if not errors:
        if page < 1:
            errors["page"] = "Must be >= 1."
        if per_page < 1:
            errors["per_page"] = "Must be >= 1."
        elif per_page > cfg["PAGINATION_MAX_PER_PAGE"]:
            errors["per_page"] = f"Must be <= {cfg['PAGINATION_MAX_PER_PAGE']}."

    if errors:
        raise ValidationApiError("Invalid pagination parameters.",
                                 details={"fields": errors})
    return page, per_page


def paginate(query, serializer=lambda item: item.to_dict()) -> dict:
    """Paginate a SQLAlchemy query into a standard envelope."""
    page, per_page = get_page_args()
    total = query.order_by(None).count()
    pages = max(1, -(-total // per_page))  # ceil division, min 1
    items = query.limit(per_page).offset((page - 1) * per_page).all()

    def page_url(p):
        args = {**request.args, "page": p, "per_page": per_page}
        return url_for(request.endpoint, **args, **(request.view_args or {}))

    return {
        "data": [serializer(item) for item in items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
            "next": page_url(page + 1) if page < pages else None,
            "prev": page_url(page - 1) if page > 1 else None,
        },
    }
