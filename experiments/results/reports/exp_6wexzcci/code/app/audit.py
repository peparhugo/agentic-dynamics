"""Audit logging: writes to the audit_log table and an application logger."""
import json
import logging

from flask import g, request

from .db import get_db

logger = logging.getLogger("audit")


def init_app(app):
    handler = (logging.FileHandler(app.config["AUDIT_LOG_PATH"])
               if app.config.get("AUDIT_LOG_PATH") else logging.StreamHandler())
    handler.setFormatter(logging.Formatter("%(asctime)s AUDIT %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def audit(action: str, resource: str = None, detail: dict = None):
    actor_id = getattr(g, "current_user_id", None)
    ip = request.remote_addr if request else None
    detail_json = json.dumps(detail) if detail else None

    db = get_db()
    db.execute(
        "INSERT INTO audit_log (actor_id, action, resource, detail, ip) "
        "VALUES (?, ?, ?, ?, ?)",
        (actor_id, action, resource, detail_json, ip),
    )
    db.commit()

    logger.info(json.dumps({
        "action": action,
        "actor_id": actor_id,
        "resource": resource,
        "detail": detail,
        "ip": ip,
    }))
