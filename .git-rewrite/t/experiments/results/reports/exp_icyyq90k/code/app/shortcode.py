import secrets

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
CODE_LENGTH = 7


def generate_short_code() -> str:
    """Generate a collision-resistant short code using cryptographically random bytes.

    64^7 ≈ 4.4 trillion combinations, making collisions extremely unlikely.
    """
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
