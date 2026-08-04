import hashlib
import secrets
import time

from config import Config

_BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _base62_encode(n: int) -> str:
    if n == 0:
        return _BASE62[0]
    chars = []
    while n > 0:
        n, rem = divmod(n, 62)
        chars.append(_BASE62[rem])
    return "".join(reversed(chars))


def generate_code(url: str, length: int | None = None) -> str:
    length = length or Config.CODE_LENGTH
    hash_input = f"{url}:{time.time_ns()}:{secrets.token_hex(16)}"
    digest = hashlib.sha256(hash_input.encode()).digest()
    num = int.from_bytes(digest[:12], "big")
    encoded = _base62_encode(num)
    if len(encoded) < length:
        encoded = _BASE62[0] * (length - len(encoded)) + encoded
    return encoded[-length:]
