from flask import request, url_for


def parse_pagination_params(default_per_page=20, max_per_page=100):
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", default_per_page, type=int)

    if page < 1:
        page = 1
    if per_page < 1:
        per_page = default_per_page
    if per_page > max_per_page:
        per_page = max_per_page

    return page, per_page


def paginate_response(items, total, page, per_page, endpoint, **kwargs):
    last_page = max(1, (total + per_page - 1) // per_page)

    links = {"self": _page_url(endpoint, page, per_page, **kwargs)}

    if page > 1:
        links["first"] = _page_url(endpoint, 1, per_page, **kwargs)
        links["prev"] = _page_url(endpoint, page - 1, per_page, **kwargs)

    if page < last_page:
        links["next"] = _page_url(endpoint, page + 1, per_page, **kwargs)
        links["last"] = _page_url(endpoint, last_page, per_page, **kwargs)

    return {
        "data": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": last_page,
        },
        "links": links,
    }


def _page_url(endpoint, page, per_page, **kwargs):
    if request.host_url is None:
        host = "http://localhost"
    else:
        host = request.host_url.rstrip("/")
    try:
        path = url_for(endpoint, page=page, per_page=per_page, _external=False, **kwargs)
        return host + path
    except Exception:
        return None
