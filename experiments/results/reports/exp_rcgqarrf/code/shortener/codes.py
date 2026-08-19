from math import gcd


ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
WIDTH = 7
SPACE = len(ALPHABET) ** WIDTH
MULTIPLIER = 1_234_567_891
OFFSET = 987_654_321

if gcd(MULTIPLIER, SPACE) != 1:
    raise RuntimeError("code permutation multiplier must be coprime to code space")


def code_for_id(identifier: int) -> str:
    """Map a database identity bijectively into the seven-character code space."""
    if identifier < 1 or identifier >= SPACE:
        raise ValueError("URL identity exceeds available code space")

    value = (identifier * MULTIPLIER + OFFSET) % SPACE
    characters = []
    for _ in range(WIDTH):
        value, remainder = divmod(value, len(ALPHABET))
        characters.append(ALPHABET[remainder])
    return "".join(reversed(characters))
