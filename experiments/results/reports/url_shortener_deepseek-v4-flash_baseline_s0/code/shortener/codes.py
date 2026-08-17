import secrets

ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"

DEFAULT_CODE_LENGTH = 6
MAX_RETRIES = 100


class CodeGenerator:
    """Generates collision-resistant short codes.

    Collision resistance is achieved by checking each candidate against the
    persistence layer and retrying with fresh randomness. As a last resort the
    code length is extended, guaranteeing progress.
    """

    def __init__(self, exists_fn, alphabet=ALPHABET, length=DEFAULT_CODE_LENGTH):
        self.exists_fn = exists_fn
        self.alphabet = alphabet
        self.length = length

    def _random(self, length):
        return "".join(secrets.choice(self.alphabet) for _ in range(length))

    def generate(self):
        length = self.length
        for attempt in range(MAX_RETRIES):
            candidate = self._random(length)
            if not self.exists_fn(candidate):
                return candidate
        for _ in range(MAX_RETRIES):
            length += 1
            candidate = self._random(length)
            if not self.exists_fn(candidate):
                return candidate
        raise RuntimeError("could not allocate a unique short code")
