import base64
import hashlib
import hmac
import os
import re
from datetime import datetime, timezone

ALLOWED_STATUSES = ["pending", "in_progress", "completed", "cancelled"]

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_ITERATIONS = 100_000


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def hash_password(password):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password, stored):
    try:
        salt_b64, dk_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return hmac.compare_digest(actual, expected)


def parse_date(value, field="due_date"):
    if value is None or value == "":
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"invalid {field}: expected ISO date (YYYY-MM-DD)")


def validate_status(value):
    if value not in ALLOWED_STATUSES:
        raise ValueError(
            f"invalid status '{value}'; must be one of {', '.join(ALLOWED_STATUSES)}"
        )
    return value
