import secrets
import string

ALPHABET = string.ascii_letters + string.digits  # base62
MAX_ATTEMPTS_PER_LENGTH = 5
MAX_LENGTH_BUMPS = 4


class CollisionError(RuntimeError):
    """Raised if a unique short code could not be generated."""


def _random_code(length):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def generate_short_code(storage, length=6):
    """Generate a short code that does not already exist in storage.

    Collisions are resolved by retrying with fresh random codes; if a
    length is exhausted repeatedly the code length is increased, which
    exponentially grows the available keyspace (62^length) and drives the
    collision probability towards zero.
    """
    current_length = length
    for _ in range(MAX_LENGTH_BUMPS):
        for _ in range(MAX_ATTEMPTS_PER_LENGTH):
            candidate = _random_code(current_length)
            if not storage.code_exists(candidate):
                return candidate
        current_length += 1
    raise CollisionError("unable to generate a unique short code")


def is_valid_custom_code(code):
    return bool(code) and all(c in ALPHABET for c in code) and 3 <= len(code) <= 32
