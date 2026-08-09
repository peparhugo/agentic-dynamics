import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-dev-secret-change-in-production")
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hour
    DATABASE = os.environ.get("DATABASE", "tasks.db")
    PAGE_SIZE_DEFAULT = 20
    PAGE_SIZE_MAX = 100
