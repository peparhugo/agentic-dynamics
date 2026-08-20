"""Control Room services (refactor-repair Debt-1).

Business logic extracted from ``server.py``, each module one responsibility:

* ``design_sessions`` — the ``DesignSessionManager`` (spec drafting, matrix, save, run).
* ``supervisor`` — retained supervisor-flag read / review / authorize / actuation.
* ``telemetry`` — retained-window snapshot, event sampling, and the SSE envelope.
* ``registry`` — the cached read of the compacted manifest registry.
* ``mutations`` — the JSON trust boundary + idempotency helpers shared by every mutating route.

Services access the shared server context (Redis, paths, constants) through ``server.*`` so the
tests' ``monkeypatch.setattr(server, …)`` behaviour is preserved.
"""
