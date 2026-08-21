"""CAP I1–I3 — the fact reducers package (reserved home).

Will hold ``spec_status/v1`` (I1), the ledger reducers ``attempt_facts/v1`` / ``job_facts/v1``
(I2), and the workflow reducer ``workflow_facts/v1`` / ``policy_facts/v1`` (I3). Frozen until
post-consolidation CAP implementation (``ARCHITECTURE.md`` §4); the home exists so the
implementation is drop-in.
"""

# reserved for CAP I1-I3
