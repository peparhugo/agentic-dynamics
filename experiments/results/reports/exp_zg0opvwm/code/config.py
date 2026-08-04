import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ACCESS_TOKEN_EXPIRES = 900  # 15 minutes
JWT_REFRESH_TOKEN_EXPIRES = 604800  # 7 days
JWT_ALGORITHM = "HS256"
SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
SQLALCHEMY_TRACK_MODIFICATIONS = False
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
RATE_LIMIT_LOGIN = (5, 60)  # 5 attempts per 60 seconds per IP
