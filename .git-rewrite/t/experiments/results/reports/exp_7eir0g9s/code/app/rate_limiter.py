from flask import request, current_app
from time import time
from threading import Lock
from werkzeug.exceptions import TooManyRequests

# Simple in-memory sliding-window rate limiter. Keys are either user:<sub> or ip:<addr>
_buckets = {}
_lock = Lock()

def _prune(timestamps, window):
    cutoff = time() - window
    while timestamps and timestamps[0] <= cutoff:
        timestamps.pop(0)

def rate_limit_middleware():
    # Determine key
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        # try to extract sub from token without verifying signature to avoid importing jwt here
        token = auth.split(' ', 1)[1].strip()
        # key for authenticated users
        key = f'user:{token}'
        window = 60
        limit = 30
    else:
        key = f'ip:{request.remote_addr or "unknown"}'
        window = 60
        limit = 10

    with _lock:
        bucket = _buckets.setdefault(key, [])
        _prune(bucket, window)
        if len(bucket) >= limit:
            raise TooManyRequests('rate limit exceeded')
        bucket.append(time())
