import secrets
import string

ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 7
MAX_GENERATION_ATTEMPTS = 10


def generate_short_code(length: int = CODE_LENGTH) -> str:
    chars = []
    for _ in range(length):
        chars.append(secrets.choice(ALPHABET))
    return "".join(chars)
