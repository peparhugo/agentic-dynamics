import os

os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://")

import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    import app as app_module

    app_module.limiter.reset()
    yield
    app_module.limiter.reset()
