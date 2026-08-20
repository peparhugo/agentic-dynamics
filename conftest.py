import pytest
from flask_limiter.extension import STRATEGIES
from flask_limiter.wrappers import LimitGroup
from limits.storage import MemoryStorage

import app as app_module


def set_default_limit(limit_str: str) -> None:
    limiter = app_module.limiter
    limiter.limit_manager.set_default_limits(
        [LimitGroup(limit_provider=limit_str, key_function=limiter._key_func)]
    )


@pytest.fixture(autouse=True)
def _memory_rate_limiter():
    limiter = app_module.limiter
    storage = MemoryStorage()
    limiter._storage = storage
    limiter._limiter = STRATEGIES[limiter._strategy](storage)
    set_default_limit("100 per minute")
    yield
