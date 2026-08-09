"""Audit logging helper.

Writes an AuditLog row for security-relevant actions (auth events and
resource mutations). Reads are not audited by default.
"""
import json

from flask import request

from .extensions import db
from .models import AuditLog


def audit(action, resource, resource_id=None, user_id=None, detail=None):
    """Record an audit entry. Committed with the surrounding transaction."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        resource_id=str(resource_id) if resource_id is not None else None,
        ip_address=request.remote_addr if request else None,
        detail=json.dumps(detail) if isinstance(detail, (dict, list)) else detail,
    )
    db.session.add(entry)
    return entry
