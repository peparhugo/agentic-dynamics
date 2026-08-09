from typing import Any
from flask_sqlalchemy.pagination import Pagination


def paginate(query, page: int = 1, per_page: int = 20) -> dict[str, Any]:
    pagination: Pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "items": [item.to_dict() for item in pagination.items],
        "meta": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    }
