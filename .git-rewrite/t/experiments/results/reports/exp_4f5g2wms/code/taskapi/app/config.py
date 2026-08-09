import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    JWT_SECRET = os.environ.get("JWT_SECRET", "jwt-secret-change-in-production")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24
    DATABASE = os.environ.get("DATABASE_PATH", "taskapi.db")
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
