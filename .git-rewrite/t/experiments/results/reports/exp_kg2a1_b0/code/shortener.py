import secrets
import string
from db import code_exists

ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 7
MAX_ATTEMPTS = 8


def _generate_code():
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def generate_unique_code(db_path):
    for _ in range(MAX_ATTEMPTS):
        code = _generate_code()
        if not code_exists(db_path, code):
            return code
    raise RuntimeError("Failed to generate a unique short code after max attempts")
