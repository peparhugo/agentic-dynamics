import secrets
import string

from app.models import URL

ALPHABET = string.ascii_letters + string.digits  # base62
MAX_ATTEMPTS_PER_LENGTH = 5


def _random_code(length):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def generate_unique_code(min_length=6, max_length=12):
    """Generate a short code that does not collide with any existing one.

    Uses cryptographically secure randomness (secrets module) over a base62
    alphabet. On repeated collisions at a given length the length is grown,
    which drives the collision probability towards zero (62^n possibilities).
    """
    length = min_length
    while length <= max_length:
        for _ in range(MAX_ATTEMPTS_PER_LENGTH):
            candidate = _random_code(length)
            if URL.query.filter_by(short_code=candidate).first() is None:
                return candidate
        length += 1
    raise RuntimeError("Unable to generate a unique short code")


def is_valid_code(code):
    if not code or not (1 <= len(code) <= 16):
        return False
    return all(ch in ALPHABET for ch in code)


def is_valid_url(url):
    from urllib.parse import urlparse

    if not url or len(url) > 4096:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)
