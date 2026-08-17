from flask import jsonify


def error_response(message, status_code):
    return jsonify({"error": message}), status_code


def paginate_query(query, page, per_page):
    page = max(int(page or 1), 1)
    per_page = min(max(int(per_page or 10), 1), 100)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "items": [item.to_dict() for item in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_prev": pagination.has_prev,
            "has_next": pagination.has_next,
        },
    }
