from cryptography.fernet import Fernet
import base64
import hashlib

from app.config import settings


def _get_fernet() -> Fernet:
    key_bytes = settings.ENCRYPTION_KEY.encode()
    derived = base64.urlsafe_b64encode(hashlib.sha256(key_bytes).digest())
    return Fernet(derived)


def encrypt_value(plaintext: str) -> str:
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def mask_account_number(number: str, visible: int = 4) -> str:
    if len(number) <= visible:
        return "*" * len(number)
    return "*" * (len(number) - visible) + number[-visible:]
