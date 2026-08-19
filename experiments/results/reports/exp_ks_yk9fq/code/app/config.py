import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-key-change-me")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_MINUTES = int(os.environ.get("JWT_EXPIRATION_MINUTES", "60"))
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(os.getcwd(), "tasks.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET_KEY = "test-jwt-secret-key-that-is-long-enough-123456"
    SECRET_KEY = "test-secret"
