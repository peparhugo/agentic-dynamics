import hashlib

_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_BASE = len(_ALPHABET)


def _to_base62(number):
    if number == 0:
        return _ALPHABET[0]
    digits = []
    while number:
        number, rem = divmod(number, _BASE)
        digits.append(_ALPHABET[rem])
    return "".join(reversed(digits))


def candidate_codes(url, length=7, max_attempts=1000):
    """Yield deterministic (code, salt) candidates derived from the URL's
    content hash. The same url always produces the same sequence, so
    resolving a collision by advancing the salt is itself deterministic
    and repeatable -- no randomness, no retry-until-lucky guessing.
    """
    for salt in range(max_attempts):
        digest = hashlib.sha256(f"{salt}:{url}".encode("utf-8")).digest()
        number = int.from_bytes(digest[:8], "big")
        code = _to_base62(number)[:length].rjust(length, _ALPHABET[0])
        yield code, salt
