from flask import current_app, request, url_for

from .schemas import PaginationQuerySchema


def paginate(query, serializer=lambda item: item.to_dict()):
    """Paginate a SQLAlchemy query using page/per_page query params.

    Returns a dict with items plus pagination metadata and navigation links.
    """
    params = PaginationQuerySchema().load(request.args, partial=True, unknown="exclude")
    page = params["page"]
    per_page = params["per_page"] or current_app.config["DEFAULT_PAGE_SIZE"]
    per_page = min(per_page, current_app.config["MAX_PAGE_SIZE"])

    result = query.paginate(page=page, per_page=per_page, error_out=False)

    def link(p):
        args = {**request.args, "page": p, "per_page": per_page}
        return url_for(request.endpoint, **request.view_args, **args)

    return {
        "items": [serializer(item) for item in result.items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_items": result.total,
            "total_pages": result.pages,
            "next": link(result.next_num) if result.has_next else None,
            "prev": link(result.prev_num) if result.has_prev else None,
        },
    }
