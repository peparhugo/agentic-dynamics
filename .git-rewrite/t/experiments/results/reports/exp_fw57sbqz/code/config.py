import os


class Config:
    DB_PATH = os.environ.get("URL_SHORTENER_DB", "urls.db")
    CODE_LENGTH = int(os.environ.get("URL_SHORTENER_CODE_LENGTH", "6"))
    DEFAULT_TTL_DAYS = int(os.environ.get("URL_SHORTENER_TTL_DAYS", "90"))
    BASE_URL = os.environ.get("URL_SHORTENER_BASE_URL", "http://localhost:5000")

    RATE_LIMIT_REQUESTS = int(os.environ.get("URL_SHORTENER_RATE_REQUESTS", "30"))
    RATE_LIMIT_WINDOW_SEC = int(os.environ.get("URL_SHORTENER_RATE_WINDOW", "60"))

    CREATE_RATE_LIMIT_REQUESTS = int(
        os.environ.get("URL_SHORTENER_CREATE_RATE_REQUESTS", "10")
    )
    CREATE_RATE_LIMIT_WINDOW_SEC = int(
        os.environ.get("URL_SHORTENER_CREATE_RATE_WINDOW", "60")
    )
