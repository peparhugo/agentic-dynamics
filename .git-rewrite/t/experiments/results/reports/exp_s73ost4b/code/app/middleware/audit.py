import logging
import json
from datetime import datetime, timezone
from functools import wraps

from flask import request, g, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

audit_logger = logging.getLogger("audit")
audit_handler = logging.StreamHandler()
audit_handler.setFormatter(logging.Formatter("[AUDIT] %(asctime)s %(message)s"))
audit_logger.addHandler(audit_handler)
audit_logger.setLevel(logging.INFO)


def audit_log(action: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            response = fn(*args, **kwargs)

            user_id = None
            try:
                verify_jwt_in_request(optional=True)
                user_id = get_jwt_identity()
            except Exception:
                pass

            entry = {
                "action": action,
                "user_id": user_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code if hasattr(response, "status_code")
                                else response[1] if isinstance(response, tuple) else 200,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            audit_logger.info(json.dumps(entry))
            return response

        return wrapper

    return decorator
