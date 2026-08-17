import os


# The application uses Redis by default; unit tests use an isolated local store.
os.environ.setdefault("RATE_LIMIT_STORAGE_URI", "memory://")
