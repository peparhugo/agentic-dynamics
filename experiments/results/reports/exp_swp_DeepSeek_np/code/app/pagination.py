from flask import current_app, request

from .errors import ValidationError


def _int_param(name, default, minimum, maximum):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValidationError(
            f"Query parameter '{name}' must be an integer.",
            fields={name: "Must be an integer."},
        )
    if value < minimum:
        return minimum
    if maximum is not None and value > maximum:
        return maximum
    return value


def get_page():
    return _int_param("page", 1, 1, None)


def get_per_page():
    default = current_app.config.get("DEFAULT_PAGE_SIZE", 20)
    maximum = current_app.config.get("MAX_PAGE_SIZE", 100)
    return _int_param("per_page", default, 1, maximum)


def paginate(query):
    """Apply pagination to a query and return (items, meta)."""
    page = get_page()
    per_page = get_per_page()

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    meta = {
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "total_pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }
    return pagination.items, meta
