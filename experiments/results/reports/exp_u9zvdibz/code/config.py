import os

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production-please")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100
