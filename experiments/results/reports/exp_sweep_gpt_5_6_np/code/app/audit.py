from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from .extensions import db
from .models import AuditLog
from .validation import pagination_args


audit_bp = Blueprint("audit", __name__, url_prefix="/v1/audit-logs")


@audit_bp.get("")
@audit_bp.get("/")
@jwt_required()
def list_audit_logs():
    page, per_page = pagination_args()
    query = (
        db.select(AuditLog)
        .where(AuditLog.user_id == int(get_jwt_identity()))
        .order_by(AuditLog.id.desc())
    )
    result = db.paginate(query, page=page, per_page=per_page, error_out=False)
    return jsonify(
        audit_logs=[entry.to_dict() for entry in result.items],
        pagination={
            "page": result.page,
            "per_page": result.per_page,
            "total": result.total,
            "pages": result.pages,
            "has_next": result.has_next,
            "has_prev": result.has_prev,
        },
    )
