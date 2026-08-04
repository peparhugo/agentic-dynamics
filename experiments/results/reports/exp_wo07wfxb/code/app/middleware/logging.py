import os
import json
import datetime
import threading
from flask import request, g, current_app


_lock = threading.Lock()


def audit_log(event, **kwargs):
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": event,
        **kwargs,
    }
    user = g.get("current_user")
    if user:
        entry["user_id"] = user["id"]
        entry["username"] = user.get("username")
    entry["ip"] = request.remote_addr
    entry["method"] = request.method
    entry["path"] = request.path

    log_file = current_app.config.get("AUDIT_LOG_FILE", "audit.log")
    with _lock:
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")


def register_request_logging(app):
    @app.before_request
    def log_request_start():
        g.request_start = datetime.datetime.now(datetime.timezone.utc)

    @app.after_request
    def log_request_end(response):
        elapsed = None
        start = g.pop("request_start", None)
        if start:
            elapsed = (
                datetime.datetime.now(datetime.timezone.utc) - start
            ).total_seconds() * 1000

        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "event": "request",
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "elapsed_ms": round(elapsed, 2) if elapsed else None,
            "ip": request.remote_addr,
        }
        user = g.get("current_user")
        if user:
            entry["user_id"] = user["id"]
            entry["username"] = user.get("username")

        if current_app.config.get("TESTING"):
            return response

        log_file = current_app.config.get("AUDIT_LOG_FILE", "audit.log")
        with _lock:
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        return response
