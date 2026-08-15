from flask import current_app, jsonify, request


def error_response(message, status_code=400, errors=None):
    payload = {"error": message}
    if errors:
        payload["details"] = errors
    return jsonify(payload), status_code


def paginate_query(query, serializer):
    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(request.args.get("per_page", current_app.config["DEFAULT_PAGE_SIZE"]))
    except (TypeError, ValueError):
        per_page = current_app.config["DEFAULT_PAGE_SIZE"]

    page = max(page, 1)
    per_page = min(max(per_page, 1), current_app.config["MAX_PAGE_SIZE"])

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return {
        "items": [serializer(item) for item in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total_items": pagination.total,
            "total_pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    }
