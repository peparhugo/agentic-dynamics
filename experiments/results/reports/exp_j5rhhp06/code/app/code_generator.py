import secrets
import string
import hashlib
import time
from app.database import code_exists

ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 7
MAX_RETRIES = 5


def _generate_code_from_bytes(data: bytes) -> str:
    num = int.from_bytes(data, "big")
    code = []
    for _ in range(CODE_LENGTH):
        num, rem = divmod(num, len(ALPHABET))
        code.append(ALPHABET[rem])
    return "".join(reversed(code))


def generate_short_code(url: str) -> str:
    for attempt in range(MAX_RETRIES):
        random_bytes = secrets.token_bytes(8)
        timestamp_bytes = int(time.time_ns()).to_bytes(8, "big")
        url_hash = hashlib.sha256(url.encode()).digest()
        combined = hashlib.sha256(random_bytes + timestamp_bytes + url_hash).digest()
        code = _generate_code_from_bytes(combined)
        if not code_exists(code):
            return code
    random_bytes = secrets.token_bytes(16)
    code = _generate_code_from_bytes(random_bytes)
    if not code_exists(code):
        return code
    for attempt in range(MAX_RETRIES):
        random_bytes = secrets.token_bytes(16)
        code = _generate_code_from_bytes(random_bytes)
        if not code_exists(code):
            return code
    raise RuntimeError("Failed to generate a unique short code after maximum retries")
