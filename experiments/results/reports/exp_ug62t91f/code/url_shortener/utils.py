import secrets

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def generate_code(length=6):
    """Return a cryptographically-random short code from a base62 alphabet."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))
