"""Audit logging.

Records who did what, when, from where, and the outcome. Entries go to
the in-memory store (queryable via the admin API) and to a standard
Python logger for shipping to external systems.
"""
import logging
from datetime import datetime, timezone

from flask import current_app, g, request

audit_logger = logging.getLogger("api.audit")


def record_audit(action, target=None, outcome="success", extra=None):
    user = getattr(g, "current_user", None)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "actor_id": user["id"] if user else None,
        "actor": user["username"] if user else "anonymous",
        "target": target,
        "outcome": outcome,
        "remote_addr": request.remote_addr if request else None,
        "method": request.method if request else None,
        "path": request.path if request else None,
        "extra": extra or {},
    }
    store = current_app.extensions["store"]
    store.add_audit(entry)
    audit_logger.info(
        "action=%s actor=%s target=%s outcome=%s path=%s",
        action, entry["actor"], target, outcome, entry["path"],
    )
    return entry
