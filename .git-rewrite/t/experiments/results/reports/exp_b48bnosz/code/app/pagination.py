"""Pagination helper producing a consistent envelope with navigation links."""
from flask import current_app, request, url_for

from .errors import ApiError
from .schemas import PaginationSchema


def paginate(query, serializer=lambda obj: obj.to_dict()):
    args = PaginationSchema().load(request.args)
    page = args["page"]
    per_page = args["per_page"] or current_app.config["DEFAULT_PAGE_SIZE"]
    max_per_page = current_app.config["MAX_PAGE_SIZE"]
    if per_page > max_per_page:
        raise ApiError(
            f"per_page must not exceed {max_per_page}.",
            status_code=400,
            code="invalid_pagination",
        )

    p = query.paginate(page=page, per_page=per_page, error_out=False)

    def page_url(page_num):
        args = request.args.to_dict()
        args.update({"page": page_num, "per_page": per_page})
        return url_for(request.endpoint, **request.view_args, **args, _external=False)

    return {
        "data": [serializer(item) for item in p.items],
        "meta": {
            "page": page,
            "per_page": per_page,
            "total_items": p.total,
            "total_pages": p.pages,
        },
        "links": {
            "self": page_url(page),
            "next": page_url(p.next_num) if p.has_next else None,
            "prev": page_url(p.prev_num) if p.has_prev else None,
            "first": page_url(1),
            "last": page_url(p.pages or 1),
        },
    }
