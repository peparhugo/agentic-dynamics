import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import app as app_module


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Clear this app's rate-limit counters before every test.

    Counters live in Redis and persist across test runs (and across the
    other apps sharing this Redis instance), so without a reset, tests
    that hit /tasks or /auth/* many times would accumulate hits across
    unrelated tests and eventually trip 429s that have nothing to do with
    the rate-limiting tests themselves. Limiter.reset() only clears keys
    under this app's own key_prefix, so it's safe on a shared Redis.
    """
    app_module.limiter.reset()
    yield
