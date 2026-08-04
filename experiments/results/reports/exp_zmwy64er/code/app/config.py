import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
SQLALCHEMY_TRACK_MODIFICATIONS = False
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URL", "memory://")
RATELIMIT_DEFAULT = "100 per minute"
RATELIMIT_AUTH_LOGIN = "10 per minute"
PAGE_SIZE_DEFAULT = 10
PAGE_SIZE_MAX = 100
