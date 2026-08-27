"""Security primitives for handling sensitive financial data.

Financial aggregators must never store plaintext credentials or account
numbers. This module provides:

* Symmetric encryption (Fernet) for bank credentials / access tokens.
* Tokenization of account numbers (vault-backed token mapping).
* PII masking for display and audit logs.
* Password hashing via PBKDF2-HMAC-SHA256.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
from typing import Dict, Optional

from cryptography.fernet import Fernet, InvalidToken


class EncryptionError(Exception):
    """Raised when a value cannot be encrypted/decrypted."""


class TokenVault:
    """Maps sensitive account numbers to opaque tokens.

    The vault stores the encrypted value and hands out a random token that is
    safe to store elsewhere (logs, downstream systems). Only the vault can map
    a token back to its real value.
    """

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)
        self._token_to_value: Dict[str, str] = {}
        self._value_to_token: Dict[str, str] = {}

    def tokenize(self, value: str) -> str:
        """Return an opaque token for ``value``, registering it in the vault."""
        value = str(value)
        if value in self._value_to_token:
            return self._value_to_token[value]
        token = "tok_" + os.urandom(16).hex()
        self._token_to_value[token] = self._fernet.encrypt(value.encode()).decode()
        self._value_to_token[value] = token
        return token

    def detokenize(self, token: str) -> str:
        """Resolve a token back to its original value."""
        encrypted = self._token_to_value.get(token)
        if encrypted is None:
            raise EncryptionError(f"unknown token: {token}")
        return self._fernet.decrypt(encrypted.encode()).decode()


class CredentialCipher:
    """Encrypts and decrypts bank credentials / access tokens."""

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        if not isinstance(plaintext, str):
            plaintext = str(plaintext)
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:  # pragma: no cover - defensive
            raise EncryptionError("decryption failed") from exc


def generate_key() -> bytes:
    """Generate a fresh Fernet key (used at deploy time, persisted in a KMS)."""
    return Fernet.generate_key()


def hash_password(password: str, salt: Optional[bytes] = None, iterations: int = 100_000) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256.

    Returns a self-describing string ``pbkdf2_sha256$iterations$salt$hash`` so
    the parameters can be upgraded transparently later.
    """
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode(),
        base64.urlsafe_b64encode(digest).decode(),
    )


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time password verification."""
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        salt_bytes = base64.urlsafe_b64decode(salt.encode())
        expected_bytes = base64.urlsafe_b64decode(expected.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt_bytes, int(iterations))
        return hmac.compare_digest(actual, expected_bytes)
    except (ValueError, TypeError):
        return False


# --- PII masking -----------------------------------------------------------

_ACCOUNT_RE = re.compile(r"\b\d{10,19}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")


def mask_account_number(number: str, visible: int = 4) -> str:
    """Mask an account number, showing only the last ``visible`` digits."""
    number = str(number)
    if len(number) <= visible:
        return "*" * len(number)
    return "*" * (len(number) - visible) + number[-visible:]


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return email
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def redact_text(text: str) -> str:
    """Redact account numbers, SSNs, and emails from free-form text.

    Used before writing to audit logs so sensitive data never lands in plain
    text log files.
    """
    text = _SSN_RE.sub("***-**-****", str(text))
    text = _ACCOUNT_RE.sub(lambda m: mask_account_number(m.group(0)), text)
    text = _EMAIL_RE.sub(lambda m: mask_email(m.group(0)), text)
    return text
