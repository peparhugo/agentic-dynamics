from time import time
from flask import current_app, request, jsonify

"""
Simple in-memory rate limiter keyed by IP. For tests and single-process usage only.
We expose helper functions so the login view can record attempts only on failed auth.
"""
ATTEMPTS = {}


def _store_for_app():
    """Return the per-app attempts store (dict of ip -> [timestamps])."""
    from flask import current_app
    app_key = str(id(current_app))
    if app_key not in ATTEMPTS:
        ATTEMPTS[app_key] = {}
    return ATTEMPTS[app_key]


def is_blocked(ip, identifier=None):
    from time import time
    window = 60
    now = int(time())
    store = _store_for_app()
    key = ip if not identifier else f"{ip}:{identifier}"
    attempts = store.get(key, [])
    attempts = [t for t in attempts if t > now - window]
    store[key] = attempts
    limit = __import__('flask').current_app.config.get('RATE_LIMIT_LOGIN_PER_MINUTE', 5)
    return len(attempts) >= limit


def record_attempt(ip, identifier=None):
    from time import time
    now = int(time())
    store = _store_for_app()
    key = ip if not identifier else f"{ip}:{identifier}"
    attempts = store.get(key, [])
    attempts.append(now)
    store[key] = attempts


def reset():
    ATTEMPTS.clear()


def clear_attempts_for_ip(ip, identifier=None):
    store = _store_for_app()
    key = ip if not identifier else f"{ip}:{identifier}"
    if key in store:
        store[key] = []
