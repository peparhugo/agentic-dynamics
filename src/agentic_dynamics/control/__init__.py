"""Control — the emerging control system (critique system 5).

Ownership: routing (``routing``/``step_routing``), the signal store, the observe-only
supervisor (``supervisor``), telemetry (``live``), pipeline status + queue steering, the
observation/actuation producers, and (since I0–I7) the Context Abstraction Plane —
``docs/designs/current/context_abstraction_design.md``.

The CAP pipe, increment by increment (each module's own docstring is the authority; this is the
map): ``facts.py`` (I0 — ``CanonicalFact``/``FACT_PREDICATES``/``EPISTEMIC_MAP``/``verify_chain``,
zero call sites by design) → ``reducers/`` (I1–I3 — deterministic versioned reducers minting
facts from evidence; ``REDUCERS``) → ``context_compiler.py`` (I4 — ``compile_context()``:
contract + scope → a frozen ``ControlContext`` snapshot; read-only, wired opt-in via
``run_workflow.py --cap-snapshot``) → ``core.contracts`` (I5 — ``FactRequirement`` +
``validate_fact_contracts``, the fact-level ``requires``/``produces`` gate; the REAL gate with
live registries is ``context_compiler.validate_spec_fact_contracts``) → ``rules.py`` +
``validator.py`` + ``decisions.py`` (I6 — ``route_next_job_v1`` proposes ``{route, continue}``
from a snapshot; ``validate_decision`` admits/refuses it via checks C1-C10;
``make_shadow_router`` runs both BESIDE ``step_routing.route_step`` and records the proposal —
``step_routing`` always wins, wired opt-in via ``--cap-shadow``) → ``rules.make_applying_router``
(I7 — the apply seam: applies the plane's ``route`` choice ONLY when a freshly re-validated
decision is admitted; falls back to ``step_routing`` on any refusal; wired via the PER-SPEC
``workflow.params.control_route: true`` opt-in, never a CLI default).

**Every CAP seam is OFF by default and stays that way until an operator explicitly flips it.**
No committed spec sets ``control_route: true`` (design §9 I7: "opt in only after the shadow
comparison shows non-inferior loss" — that campaign data does not exist yet); see
``docs/context_abstraction/implementation_notes.md`` for the flip procedure and
``scripts/{context_snapshot_report,shadow_decision_report,decision_arm_comparison}.py`` for the
measured evidence an operator needs before flipping it.

Control consumes facts, not arbitrary retrieved text (rec 8): it must not import
``knowledge.retrieval`` or ``knowledge.prompt_constructor``.
"""

from . import (
    actuation_ingestion,
    evidence_analyzer,
    live,
    observation_ingestion,
    pipeline_status,
    queue_reinterleave,
    routing,
    signal_store,
    step_routing,
    supervisor,
)

__all__ = ['actuation_ingestion', 'evidence_analyzer', 'live', 'observation_ingestion', 'pipeline_status', 'queue_reinterleave', 'routing', 'signal_store', 'step_routing', 'supervisor']
