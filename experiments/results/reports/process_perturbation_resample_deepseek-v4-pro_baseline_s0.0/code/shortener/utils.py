import secrets
import string
from urllib.parse import urlparse

ALPHABET = string.ascii_letters + string.digits
MAX_URL_LENGTH = 2048


def generate_short_code(length: int = 6) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def validate_url(url: str) -> bool:
    if not isinstance(url, str):
        return False
    if not url or len(url) > MAX_URL_LENGTH:
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)
