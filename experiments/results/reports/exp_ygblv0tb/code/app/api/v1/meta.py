from flask import jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from ...models import AuditLog
from ...pagination import paginate
from . import api_v1


@api_v1.get("/health")
def health():
    return jsonify({"status": "ok", "version": "v1"})


@api_v1.get("/audit-logs")
@jwt_required()
def list_audit_logs():
    """Return the caller's own audit trail, paginated."""
    user_id = int(get_jwt_identity())
    query = (AuditLog.query
             .filter_by(user_id=user_id)
             .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()))
    return jsonify(paginate(query))
