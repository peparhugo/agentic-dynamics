import logging
from flask import request, g

logger = logging.getLogger('audit')
handler = logging.FileHandler('audit.log')
formatter = logging.Formatter('%(asctime)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def audit_log(response):
    # Called after each request
    user = getattr(g, 'user', None)
    ip = request.remote_addr
    method = request.method
    path = request.path
    status = response.status_code
    logger.info('user=%s ip=%s method=%s path=%s status=%s', user, ip, method, path, status)
    return response
