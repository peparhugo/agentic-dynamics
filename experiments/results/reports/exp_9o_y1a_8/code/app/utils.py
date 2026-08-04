from datetime import datetime, timezone

from flask import request
from flask_jwt_extended import create_access_token, get_jwt_identity
from marshmallow import ValidationError
from werkzeug.security import generate_password_hash, check_password_hash

from app.models import db, User, Category, Task


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password_hash, password):
    return check_password_hash(password_hash, password)


def generate_token(user_id):
    return create_access_token(identity=user_id)


def get_current_user():
    user_id = get_jwt_identity()
    return db.session.get(User, user_id)


def paginate_query(query, page, per_page, schema_class=None):
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    data = []
    for item in paginated.items:
        d = item.to_dict()
        if schema_class:
            d = schema_class.dump(d)
        data.append(d)
    return {
        "data": data,
        "pagination": {
            "page": paginated.page,
            "per_page": paginated.per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "has_next": paginated.has_next,
            "has_prev": paginated.has_prev,
        },
    }


def apply_task_filters(query, status=None, priority=None, category_id=None,
                       assigned_to_id=None, search=None, sort_by=None, sort_order=None):
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    if category_id:
        query = query.filter(Task.category_id == category_id)
    if assigned_to_id:
        query = query.filter(Task.assigned_to_id == assigned_to_id)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            db.or_(Task.title.ilike(pattern), Task.description.ilike(pattern))
        )

    sort_column = getattr(Task, sort_by or "created_at", Task.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    return query


def parse_date(dt_value):
    if dt_value is None:
        return None
    if isinstance(dt_value, datetime):
        return dt_value
    if isinstance(dt_value, str):
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                naive = datetime.strptime(dt_value, fmt)
                return naive.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        raise ValidationError(f"Cannot parse date: {dt_value}")
    return dt_value
