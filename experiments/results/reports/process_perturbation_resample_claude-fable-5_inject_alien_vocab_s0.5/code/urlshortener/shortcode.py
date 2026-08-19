import secrets
import string

ALPHABET = string.ascii_letters + string.digits  # base62
DEFAULT_LENGTH = 7
MAX_ATTEMPTS_PER_LENGTH = 10


def generate_code(length=DEFAULT_LENGTH):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def generate_unique_code(exists_fn, length=DEFAULT_LENGTH):
    """Generate a short code guaranteed not to collide with an existing one.

    Retries with the requested length a bounded number of times; if the
    keyspace is saturated it widens the code by one character and tries
    again, so callers never receive a colliding code.
    """
    current_length = length
    while True:
        for _ in range(MAX_ATTEMPTS_PER_LENGTH):
            code = generate_code(current_length)
            if not exists_fn(code):
                return code
        current_length += 1
