import os

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = 3600

RATE_LIMIT_DEFAULT = "100 per minute"
RATE_LIMIT_AUTH = "5 per minute"

AUDIT_LOG_FILE = "audit.log"

ITEMS_PER_PAGE = 20
MAX_PER_PAGE = 100
