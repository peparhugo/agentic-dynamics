import hashlib
import secrets
import time

BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _base62_encode(n: int) -> str:
    if n == 0:
        return BASE62[0]
    chars = []
    while n > 0:
        n, rem = divmod(n, 62)
        chars.append(BASE62[rem])
    return "".join(reversed(chars))


def generate_short_code(length: int = 7) -> str:
    raw = f"{secrets.token_hex(8)}{time.time_ns()}"
    digest = hashlib.sha256(raw.encode()).digest()
    num = int.from_bytes(digest, "big")
    code = _base62_encode(num)
    return code[:length]


def is_collision_resistant(db_check_fn, length: int = 7, max_attempts: int = 5) -> str:
    for _ in range(max_attempts):
        code = generate_short_code(length)
        if not db_check_fn(code):
            return code
    return generate_short_code(length + 1)
