import sys
import os

# Ensure the project root is on PYTHONPATH for tests
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Expose a reference to the app's rate limiter reset if available
try:
    from app import reset_rate_limiter
except Exception:
    reset_rate_limiter = None


import pytest


@pytest.fixture(autouse=True)
def reset_rate_limiter_before_test():
    if 'reset_rate_limiter' in globals() and reset_rate_limiter:
        reset_rate_limiter()

# Import for test fixture usage
import pytest
