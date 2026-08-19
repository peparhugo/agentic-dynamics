import base64
import hashlib
import hmac


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_code(long_url: str, counter: int, secret: str, length: int = 8) -> str:
    message = f"{long_url}\x00{counter}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url(digest)[:length]
