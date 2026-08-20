"""Core — the foundation shared by every plane (tier 0 of the dependency spine).

Ownership: language profiling (``language``), filesystem/registry paths (``paths``),
session/task vocabulary (``session_types``), and shared subprocess streaming (``streaming``).

``core`` imports only the standard library (plus core siblings) — nothing from tier ≥ 1 of
the spine ``core ← experiment/measurement/runtime/knowledge ← control ← applications``.
Enforced by ``tests/test_dependency_direction.py`` (Stage 1, phase D).

Reserved (empty until post-consolidation CAP implementation, per ``ARCHITECTURE.md`` §4):
``contracts.py`` — the CAP I5 fact-contracts home.
"""

from . import language, paths, session_types, streaming



__all__ = ['language', 'paths', 'session_types', 'streaming']
