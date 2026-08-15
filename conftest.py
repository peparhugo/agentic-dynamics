import os


# Tests do not require an external Redis service; production defaults to Redis.
os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://")
