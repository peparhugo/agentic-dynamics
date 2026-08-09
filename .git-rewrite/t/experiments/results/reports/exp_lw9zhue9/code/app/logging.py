import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from flask import Request, Response


AUDIT_LOGGER_NAME = "audit" 


def init_audit_logger(app):
    log_path = Path(app.config["AUDIT_LOG_PATH"]).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(AUDIT_LOGGER_NAME)
    if not logger.handlers:
        handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3)
        fmt = logging.Formatter("%(asctime)s %(message)s")
        handler.setFormatter(fmt)
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
    # Avoid propagation to root
    logger.propagate = False


def audit_log_request(app, req: Request, resp: Response):
    # Log: method path status user/ip user_agent
    logger = logging.getLogger(AUDIT_LOGGER_NAME)
    user = getattr(req, "user_id", None) or "anon"
    ip = req.headers.get("X-Forwarded-For", req.remote_addr)
    ua = req.user_agent.string if req.user_agent else "-"
    logger.info(f"method=%s path=%s status=%s user=%s ip=%s ua=\"%s\"",
                req.method, req.path, resp.status_code, user, ip, ua)
