"""Control — the emerging control system (critique system 5).

Ownership: routing (``routing``/``step_routing``), the signal store, the observe-only
supervisor (``supervisor``), telemetry (``live``), pipeline status + queue steering, and the
observation/actuation producers.

Reserved CAP homes (empty until post-consolidation CAP implementation — ``ARCHITECTURE.md`` §4):
``facts.py`` (I0), ``reducers/`` (I1–I3), ``context_compiler.py`` (I4), ``rules.py`` +
``validator.py`` + ``decisions.py`` (I6). The I5 fact-contracts home is ``core/contracts.py``.

Control consumes facts, not arbitrary retrieved text (rec 8): it must not import
``knowledge.retrieval`` or ``knowledge.prompt_constructor``.
"""
