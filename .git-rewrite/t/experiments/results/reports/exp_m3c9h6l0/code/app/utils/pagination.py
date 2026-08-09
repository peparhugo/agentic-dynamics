from flask import request, url_for
from app.config import Config


def paginate(query, schema, endpoint=None):
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", Config.DEFAULT_PAGE_SIZE, type=int)
    per_page = min(per_page, Config.MAX_PAGE_SIZE)

    if page < 1 or per_page < 1:
        from app.utils.errors import BadRequest
        raise BadRequest("Page and per_page must be positive integers")

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    items = [schema.dump(item) for item in paginated.items]

    meta = {
        "page": paginated.page,
        "per_page": paginated.per_page,
        "total": paginated.total,
        "pages": paginated.pages,
        "has_next": paginated.has_next,
        "has_prev": paginated.has_prev,
    }

    if paginated.has_next and endpoint:
        meta["next"] = url_for(
            endpoint, page=paginated.next_num, per_page=per_page, _external=True
        )
    if paginated.has_prev and endpoint:
        meta["prev"] = url_for(
            endpoint, page=paginated.prev_num, per_page=per_page, _external=True
        )

    return {"data": items, "meta": meta}
