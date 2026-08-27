from flask import Blueprint, jsonify
from sqlalchemy import select

from .decorators import admin_required, token_required
from .extensions import db
from .models import AuditLog, User
from .validators import parse_pagination

admin_bp = Blueprint("admin", __name__)


def _pagination_body(page, per_page, total, pages, has_next, has_prev, data):
    return {
        "data": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
            "has_next": has_next,
            "has_prev": has_prev,
        },
    }


@admin_bp.get("/users")
@token_required
@admin_required
def list_users():
    page, per_page = parse_pagination()
    stmt = select(User).order_by(User.id.asc())
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    return (
        jsonify(
            _pagination_body(
                pagination.page,
                pagination.per_page,
                pagination.total,
                pagination.pages,
                pagination.has_next,
                pagination.has_prev,
                [u.to_dict() for u in pagination.items],
            )
        ),
        200,
    )


@admin_bp.get("/audit-logs")
@token_required
@admin_required
def list_audit_logs():
    page, per_page = parse_pagination()
    stmt = select(AuditLog).order_by(AuditLog.id.desc())
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    return (
        jsonify(
            _pagination_body(
                pagination.page,
                pagination.per_page,
                pagination.total,
                pagination.pages,
                pagination.has_next,
                pagination.has_prev,
                [a.to_dict() for a in pagination.items],
            )
        ),
        200,
    )
