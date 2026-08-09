def validate_required_fields(data, required):
    missing = [f for f in required if f not in data or data[f] is None]
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"
    return True, ""


def validate_status(value):
    valid = {"pending", "in_progress", "completed"}
    if value not in valid:
        return False, f"Invalid status. Must be one of: {', '.join(sorted(valid))}"
    return True, ""


def validate_priority(value):
    valid = {"low", "medium", "high", "critical"}
    if value not in valid:
        return (
            False,
            f"Invalid priority. Must be one of: {', '.join(sorted(valid))}",
        )
    return True, ""


def validate_non_empty_string(value, field_name):
    if not isinstance(value, str) or not value.strip():
        return False, f"{field_name} must be a non-empty string"
    return True, ""


def build_pagination_meta(page, per_page, total):
    total_pages = max(1, (total + per_page - 1) // per_page)
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


def parse_pagination_args(request_args, max_page_size, default_page_size):
    try:
        page = max(1, int(request_args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = max(1, int(request_args.get("per_page", default_page_size)))
    except (ValueError, TypeError):
        per_page = default_page_size

    per_page = min(per_page, max_page_size)
    return page, per_page
