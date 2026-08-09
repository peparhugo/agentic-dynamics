import json
import os
import logging
from datetime import datetime, timezone

from config import AUDIT_LOG_FILE

logger = logging.getLogger("audit")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.FileHandler(AUDIT_LOG_FILE)
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)


def log_audit(action, user=None, resource=None, status=None, details=None):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "user": user,
        "resource": resource,
        "status": status,
        "details": details or {},
    }
    logger.info(json.dumps(entry))


def clear_audit_log():
    if os.path.exists(AUDIT_LOG_FILE):
        open(AUDIT_LOG_FILE, "w").close()
