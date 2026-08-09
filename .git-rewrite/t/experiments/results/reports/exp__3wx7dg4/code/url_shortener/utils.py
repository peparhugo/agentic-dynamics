import secrets
import hashlib
import re
from urllib.parse import urlparse

ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
CODE_LENGTH = 7
MAX_GENERATION_ATTEMPTS = 5

URL_RE = re.compile(
    r"^https?://"
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,63}|"
    r"localhost|\d{1,3}(?:\.\d{1,3}){3})"
    r"(?::\d+)?(?:/.*)?$",
    re.IGNORECASE,
)


def generate_code(length: int = CODE_LENGTH) -> str:
    entropy = (length * 5 + 7) // 8
    random_bytes = secrets.token_bytes(entropy)
    hash_bytes = hashlib.sha256(random_bytes).digest()

    code = []
    for i in range(length):
        code.append(ALPHABET[hash_bytes[i] % 62])

    return "".join(code)


def validate_url(url: str) -> bool:
    return bool(URL_RE.match(url))


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.geturl()
