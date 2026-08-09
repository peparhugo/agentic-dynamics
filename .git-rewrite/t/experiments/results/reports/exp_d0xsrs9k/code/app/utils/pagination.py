from flask import request


def paginate(items: list, total: int, page: int, per_page: int) -> dict:
    total_pages = max(1, (total + per_page - 1) // per_page)

    base_url = request.base_url
    links = {"self": f"{base_url}?page={page}&per_page={per_page}"}

    if page > 1:
        links["first"] = f"{base_url}?page=1&per_page={per_page}"
        links["prev"] = f"{base_url}?page={page - 1}&per_page={per_page}"

    if page < total_pages:
        links["next"] = f"{base_url}?page={page + 1}&per_page={per_page}"
        links["last"] = f"{base_url}?page={total_pages}&per_page={per_page}"

    return {
        "data": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "links": links,
        },
    }
