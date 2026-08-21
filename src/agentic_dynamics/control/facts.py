"""CAP I0 — the fact schema + predicate registry (reserved home).

Will hold ``CanonicalFact``, ``FACT_PREDICATES``, ``EPISTEMIC_MAP``, and ``verify_chain`` —
the fact layer every reducer consumes. Frozen until post-consolidation CAP implementation
(``ARCHITECTURE.md`` §4); the home exists so the implementation is drop-in.
"""

# reserved for CAP I0
