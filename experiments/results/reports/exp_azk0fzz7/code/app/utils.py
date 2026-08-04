from __future__ import annotations

from flask import abort, jsonify, request
from functools import wraps
from typing import Callable, Tuple

from .schemas import ValidationError


def handle_validation(f: Callable):
    # Decorator to catch our ValidationError and convert to JSON response
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValidationError as e:
            return (
                jsonify({"error": "validation_error", "message": str(e), "details": e.details}),
                422,
            )
    return wrapper


def paginate(items: list[dict], page: int, per_page: int) -> Tuple[list[dict], dict]:
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    data = items[start:end]
    meta = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": (total + per_page - 1) // per_page,
    }
    return data, meta
