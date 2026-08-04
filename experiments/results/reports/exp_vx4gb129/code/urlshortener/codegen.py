import secrets
import string

ALPHABET = string.ascii_letters + string.digits
ALPHABET_LEN = len(ALPHABET)
CODE_LENGTH = 8


def generate_code() -> str:
    mask = (1 << (ALPHABET_LEN.bit_length())) - 1
    ceiling = mask // ALPHABET_LEN * ALPHABET_LEN

    while True:
        random_bytes = secrets.token_bytes(CODE_LENGTH * 2)
        result: list[str] = []
        for i in range(0, len(random_bytes), 2):
            if len(result) >= CODE_LENGTH:
                break
            byte_val = int.from_bytes(
                random_bytes[i : i + 2], byteorder="big"
            )
            masked = byte_val & mask
            if masked >= ceiling:
                continue
            result.append(ALPHABET[masked % ALPHABET_LEN])
        if len(result) == CODE_LENGTH:
            return "".join(result)
