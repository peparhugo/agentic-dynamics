import logging
import json

audit_logger = logging.getLogger('audit')
audit_logger.setLevel(logging.INFO)
fh = logging.FileHandler('audits.log')
fh.setLevel(logging.INFO)
formatter = logging.Formatter('%(message)s')
fh.setFormatter(formatter)
audit_logger.addHandler(fh)

def log_audit(obj):
    # helper to write structured json logs
    audit_logger.info(json.dumps(obj))
