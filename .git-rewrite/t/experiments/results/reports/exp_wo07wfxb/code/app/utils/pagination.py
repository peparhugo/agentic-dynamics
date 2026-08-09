def parse_pagination_args():
    from flask import request

    try:
        page = int(request.args.get("page", 1))
    except (ValueError, TypeError):
        page = 1
    try:
        per_page = int(request.args.get("per_page", 20))
    except (ValueError, TypeError):
        per_page = 20

    page = max(1, page)
    per_page = max(1, min(100, per_page))
    return page, per_page
