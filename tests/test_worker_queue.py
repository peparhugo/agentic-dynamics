"""Boundary guard for the worker's queue consumer (the 2026-09-12 review's #3).

redis-py's signature is ``brpop(keys: List, timeout=0)``; the pre-review worker called
``r.brpop(QUEUE_KEY, BATCH_QUEUE_KEY, timeout=...)``, which binds the second positional key to
``timeout`` and raises ``TypeError`` **before any I/O** — blocking both lanes behind the broad
reconnect handler. The batch unit tests exercised membership scanning, not this call, so green
suites did not settle it.

This test uses an **autospecced real client**: any call shape the real client would refuse
fails here at binding time, in CI, instead of in a live worker.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import create_autospec

import redis

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src", _ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from worker import BATCH_QUEUE_KEY, BLOCK_TIMEOUT, QUEUE_KEY, _dequeue  # noqa: E402


def test_dequeue_passes_one_keys_list_in_priority_order():
    """The ordered lane contract, in the ONE call shape redis-py accepts."""
    client = create_autospec(redis.Redis, instance=True)
    client.brpop.return_value = (QUEUE_KEY, '{"cell_id": "x"}')

    result = _dequeue(client)

    client.brpop.assert_called_once_with([QUEUE_KEY, BATCH_QUEUE_KEY], timeout=BLOCK_TIMEOUT)
    assert result == (QUEUE_KEY, '{"cell_id": "x"}')


def test_the_call_shape_would_fail_the_old_two_positional_keys_form():
    """PROOF the guard bites: the pre-review call raises against the same autospec.

    This mirrors exactly what the review reproduced — a second positional key binds to
    ``timeout`` and the real signature refuses it before I/O.
    """
    client = create_autospec(redis.Redis, instance=True)
    try:
        client.brpop(QUEUE_KEY, BATCH_QUEUE_KEY, timeout=BLOCK_TIMEOUT)
    except TypeError as exc:
        assert "timeout" in str(exc)
    else:  # pragma: no cover - the autospec would have to be wrong
        raise AssertionError("the two-positional-keys form unexpectedly bound cleanly")
