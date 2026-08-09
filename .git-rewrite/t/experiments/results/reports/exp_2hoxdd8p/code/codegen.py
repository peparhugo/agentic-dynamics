import secrets
import string
from typing import Optional
import database


ALPHANUM = string.digits + string.ascii_letters


def _random_code(length: int = 8) -> str:
    # Generate a URL-friendly, collision-resistant short code
    return ''.join(secrets.choice(ALPHANUM) for _ in range(length))


def generate_unique_code(length: int = 8) -> str:
    # Loop until we find a code not already used in the DB
    tries = 0
    while True:
        code = _random_code(length)
        tries += 1
        # naive check for collision
        existing = database.get_original_url(code)
        if existing is None:
            return code
        # Very unlikely to loop forever; cap attempts defensively
        if tries > 100:
            # Fallback to a longer code to reduce collision probability
            length += 2
            tries = 0
