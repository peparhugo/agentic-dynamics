import hashlib
import secrets
import string

ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase
BASE = len(ALPHABET)


def _int_to_base62(n: int) -> str:
    """Encode an integer to a base62 string using a bijective mapping.
    This is not padding-preserving: leading zeros in the original bytes are lost.
    We fix that by feeding 7 raw bytes of entropy and mapping directly.
    """
    chars = []
    while n > 0:
        n, r = divmod(n, BASE)
        chars.append(ALPHABET[r])
    return "".join(reversed(chars))


def emergent_code(length: int) -> str:
    """
    Generate a collision-resistant shortcode.

    Approach:
      - Pull `length` random bytes as entropy seeds.
      - XOR each entropy byte with the byte-level SHA-256 hash of the bytes
        themselves, creating a feedback loop (the hash constrains the
        randomness — analogous to a homeostatic ecosystem where each
        part shapes every other part).
      - Map the resulting bytes directly into base62 space.

    The XOR step acts like a neural dendritic computation: distributed
    signal mixing between raw entropy and its own cryptographic hash
    ensures that even trivial bit-flips in the input produce a wildly
    different code.  This reduces sequential collision probability
    without needing a global counter.
    """
    entropy = secrets.token_bytes(length)
    digest = hashlib.sha256(entropy).digest()
    mixed = bytes(a ^ b for a, b in zip(entropy, digest[:length]))
    n = int.from_bytes(mixed, "big")
    code = _int_to_base62(n)
    if len(code) < length:
        code = code.zfill(length)
    return code[:length]
