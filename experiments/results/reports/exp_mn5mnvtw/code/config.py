import os

SHORTCODE_LENGTH = int(os.getenv("SHORTCODE_LENGTH", "7"))
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
DB_PATH = os.getenv("DB_PATH", "urls.db")
RATE_LIMIT = os.getenv("RATE_LIMIT", "100/minute")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
