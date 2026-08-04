from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./mint.db"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ENCRYPTION_KEY: str = "mint-encryption-key-32-bytes!!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    BATCH_SIZE: int = 100
    ALERT_CHECK_INTERVAL_MINUTES: int = 60

    class Config:
        env_file = ".env"


settings = Settings()
