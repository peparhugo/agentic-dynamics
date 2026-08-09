"""Audit log read access (admin only)."""
from flask import jsonify
from flask_jwt_extended import get_jwt, jwt_required

from ...errors import ApiError
from ...models import AuditLog
from ...pagination import paginate
from . import bp


@bp.get("/audit-logs")
@jwt_required()
def list_audit_logs():
    if get_jwt().get("role") != "admin":
        raise ApiError("Admin access required.", status_code=403, code="forbidden")
    query = AuditLog.query.order_by(AuditLog.id.desc())
    return jsonify(paginate(query))
