"""Pagination helper producing a consistent envelope."""
from flask import current_app, request, url_for

from .schemas import PaginationQuerySchema

_query_schema = PaginationQuerySchema()


def paginate(query, serializer=lambda o: o.to_dict()):
    """Paginate a SQLAlchemy query from ?page=&per_page= query args.

    Returns a dict:
        {
          "data": [...],
          "meta": {"page", "per_page", "total", "pages"},
          "links": {"self", "next", "prev"}
        }
    Raises marshmallow.ValidationError for invalid query params (handled
    globally as a 422).
    """
    args = _query_schema.load(
        {k: v for k, v in request.args.items() if k in ("page", "per_page")}
    )
    default_pp = current_app.config["PAGINATION_DEFAULT_PER_PAGE"]
    max_pp = current_app.config["PAGINATION_MAX_PER_PAGE"]
    page = args["page"]
    per_page = min(args["per_page"] or default_pp, max_pp)

    p = query.paginate(page=page, per_page=per_page, error_out=False)

    def link(target_page):
        if target_page is None:
            return None
        params = {**request.view_args, **request.args.to_dict()}
        params.update(page=target_page, per_page=per_page)
        return url_for(request.endpoint, **params)

    return {
        "data": [serializer(obj) for obj in p.items],
        "meta": {
            "page": p.page,
            "per_page": p.per_page,
            "total": p.total,
            "pages": p.pages,
        },
        "links": {
            "self": link(p.page),
            "next": link(p.next_num if p.has_next else None),
            "prev": link(p.prev_num if p.has_prev else None),
        },
    }
