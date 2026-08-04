import time
from collections import defaultdict, deque
from functools import wraps
from flask import current_app, request
from .errors import RateLimitError

_buckets = defaultdict(deque)


def reset():
    _buckets.clear()


def rate_limit(key_prefix, max_config, window_config):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            limit = current_app.config[max_config]
            window = current_app.config[window_config]
            key = f"{key_prefix}:{request.remote_addr}"
            now = time.monotonic()
            bucket = _buckets[key]
            while bucket and bucket[0] <= now - window:
                bucket.popleft()
            if len(bucket) >= limit:
                retry = int(window - (now - bucket[0])) + 1
                raise RateLimitError(retry_after=retry)
            bucket.append(now)
            return f(*args, **kwargs)
        return wrapper
    return decorator
