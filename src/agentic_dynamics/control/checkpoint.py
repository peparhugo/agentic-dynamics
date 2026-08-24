"""CAP addendum I10 — ``SessionCheckpoint`` (design §4.1, new reserved home per design §6).

A checkpoint is the typed residue a session leaves for its successor — what closes the third gap
the frozen design named (`context_abstraction_design.md:1476-1479`): "what durable residue a
session leaves when forked". This module ships ONLY the schema (a frozen dataclass) plus the two
small, pure helpers that implement design's own D5 resolution (the DERIVED/ADVISORY payload
split); the deterministic *producer* of a checkpoint — the ``checkpoint/v1`` reducer that reads a
typed ``WorkflowRunResult`` and mints the DERIVED-grade facts — lives in its own reserved home,
``control/reducers/checkpoint.py``, exactly the same "schema here, reducer in the reducers
package" split ``control/facts.py``/``control/reducers/pattern.py`` already established for I9.

DEMOTION RULE, restated for this module specifically (design §1's own load-bearing principle,
applied a third time): *a field that names a producer that does not exist is demoted or
deferred, never silently empty.* Two fields are demoted from the addendum's OWN literal wording
(`context_abstraction_design.md:1567-1578`), both per the ACCEPTED addendum design's §4.1
resolution table and deviations D1/D2 (`docs/designs/current/context_abstraction_addendum_design.md`):

* ``verified_facts`` — the addendum text calls this DERIVED ("canonical fact ids by reference").
  **v1 demotes it to ADVISORY.** There are no canonical facts of predicate ``"fact"`` yet
  (``control/facts.py``'s ``FACT_PREDICATES`` carries no such row, and ``knowledge.SOURCE_TYPES``
  has no ``source_type="fact"`` row for arbitrary citation) — the only thing a v1 checkpoint can
  honestly populate this from is ``PhaseResult.selected_evidence_ids`` (RAG retrieval evidence,
  ``workflow_runner.py:106``), which is *retrieval* evidence, not a *canonical fact citation*.
  Marking it DERIVED here would ship a field whose provenance claim is untrue.
* ``context_snapshot_id`` — the addendum has this as a REQUIRED ``str`` (§6.4's snapshot-id
  formula). **v1 makes it ``str | None = None``**, with a NEW explicit ``snapshot_available``
  flag, because ``snapshot_id`` has no producer until the I4 Context Compiler's own snapshot
  machinery is wired to a live production call site — today it exists (``compile_context``'s
  ``ControlContext.snapshot_id``) but nothing captures it into a checkpoint. An explicit
  ``False`` flag keeps "no snapshot exists in v1" distinguishable from "a snapshot was lost".

A NOTE ON THE TASK PROMPT THAT ASKED FOR THIS MODULE: the prompt's own DELIVER text groups
``verified_facts``/``context_snapshot_id`` under "DERIVED" — this is an imprecise paraphrase of
the addendum, not the addendum itself. The accepted design's §4.1 table is unambiguous (and its
own adversarial finding F3, `context_abstraction_addendum_design.md` §9, explains exactly why a
literal DERIVED grading for these two fields is a hard-rule-4 violation: it would let an
un-produced field masquerade as a measured/derived one). This module follows the ACCEPTED DESIGN,
per this task's own GOAL line ("per the accepted addendum design"), not the prompt's shorthand
grouping — documented here, and again in ``docs/context_abstraction/implementation_notes.md``
§15, exactly as every other genuine deviation in this plane is recorded: explicitly, never
silently.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any

# ── SessionCheckpoint (design §4.1) ──────────────────────────────


@dataclass(frozen=True)
class SessionCheckpoint:
    """The typed residue one session leaves for its successor (addendum A.4, design §4.1).

    Per-field epistemic grade is documented inline; :data:`DERIVED_FIELDS` and
    :data:`ADVISORY_FIELDS` are the machine-checkable form of the same split — a test (or a
    future producer) can assert against them instead of re-reading these comments.
    """

    goal: str
    """[M] MEASURED — ``WorkflowRunResult.goal`` (``workflow_runner.py:160``), the session's own
    declared objective. Not "derived" in the reducer sense: it is copied verbatim from a field
    the runtime already records, the same grade the design's own table gives it."""

    completed: tuple[str, ...] = ()
    """DERIVED [C] — the phase names this session has finished. The addendum cites
    ``_completed_phases``'s git-log walk (`workflow_runner.py:235-254`) plus an index fallback
    (`:290-328`); BOTH are I/O (a live git repo), which a pure reducer may never perform (design
    §4.1's own purity discipline). ``checkpoint/v1`` computes an honest, non-fabricated PROXY
    instead — phase names with ``PhaseResult.status == "ok"`` in the SAME typed run artifact
    every other I2/I3 reducer already reads (`workflow_runner.py:81`) — still a real, derived
    fact, sourced differently than the addendum's own prose, documented in the reducer."""

    current_revision: str = ""
    """DERIVED [C] — ``WorkflowRunResult.git_sha`` (`workflow_runner.py:165`), the already-
    recorded commit the run's own artifact carries. Equivalent in content to what a live
    ``_git_head`` call (`workflow_runner.py:227-232`) would return for that same commit, without
    the I/O — the run artifact already recorded it once."""

    acceptance_state: str = ""
    """DERIVED [C] — ``test_executed_success`` + phase ``status`` (`workflow_runner.py:113,81`).
    ``checkpoint/v1`` renders this as one of ``verified_pass`` / ``verified_fail`` /
    ``unverified_ok`` / ``unverified_fail`` — "verified" means an independent test phase actually
    ran (`test_executed_success is not None`); ``first_pass``/``accepted`` stay UNWRITTEN
    (declared-not-written, `experiment_spec.py:175-176`) and are never fabricated into this
    field."""

    context_snapshot_id: str | None = None
    """v1: ALWAYS ``None`` — DEMOTED from the addendum's required ``str`` (deviation D2). See the
    module docstring. Read together with :attr:`snapshot_available`."""

    snapshot_available: bool = False
    """NEW (not in the addendum's own field list) — an explicit, honest marker that no
    ``context_snapshot_id`` exists in v1, so "no snapshot" is never confused with "a snapshot was
    lost/unreadable". Always ``False`` until the I4 Context Compiler gains a real capture call
    site (design D2)."""

    verified_facts: tuple[str, ...] = ()
    """v1 ADVISORY [H] — DEMOTED from the addendum's DERIVED (deviation D1). Populated (by a
    FUTURE producer, not this module) from ``PhaseResult.selected_evidence_ids``
    (`workflow_runner.py:106`) — RAG retrieval evidence, not a canonical fact citation. See the
    module docstring for why this is demoted, not just renamed."""

    open_hypotheses: tuple[str, ...] = ()
    """ADVISORY [H] — the session's own account (unchanged from the addendum). No capture
    surface exists yet; a future best-effort ``[H]`` session-summary extractor over
    ``PhaseResult.final_response`` (`workflow_runner.py:99`) would populate this — not built by
    this increment (design §7 item 8's own scope boundary)."""

    failed_approaches: tuple[str, ...] = ()
    """ADVISORY [H] — the session's own account (unchanged). Half-capturable today from
    ``PhaseResult.error``/``status`` (`workflow_runner.py:89,81`), but still a narrative
    judgment, not a measurement — stays ADVISORY regardless of how much of it is mechanically
    extractable."""

    next_action: str = ""
    """ADVISORY [H] — a PROPOSAL, never applied (design §8.6; ``AUTOMATABLE_ACTIONS`` is
    untouched by this increment — see ``control/decisions.py``). This is exactly the same
    "proposal only" doctrine every other CAP control surface follows."""


#: The fields carried by the CANONICAL ``session_checkpoint`` fact (design §4.1's DERIVED column,
#: v1 grades). This is the ONLY payload ``checkpoint/v1`` folds into the fact's ``value`` —
#: nothing ADVISORY rides along (D5, resolving adversarial finding F3: a same-fact ADVISORY
#: narrative would re-key the CANONICAL fact's identity on every narrative edit, and a controller
#: citing the checkpoint fact would receive un-citable content at fact granularity).
DERIVED_FIELDS: frozenset[str] = frozenset(
    {"goal", "completed", "current_revision", "acceptance_state",
     "context_snapshot_id", "snapshot_available"}
)

#: The fields that ride along as SEPARATE ADVISORY ``checkpoint_narrative`` records (D1 folds
#: ``verified_facts`` into this ADVISORY set too, alongside the addendum's original three —
#: same epistemic grade, same reasoning: never citable, never in the canonical payload).
ADVISORY_FIELDS: frozenset[str] = frozenset(
    {"verified_facts", "open_hypotheses", "failed_approaches", "next_action"}
)

#: Completeness guard, evaluated at import time (mirrors the same self-checking pattern
#: ``EPISTEMIC_MAP``/``FACT_PREDICATES`` rely on elsewhere): every dataclass field is graded
#: EXACTLY once — never left ungraded, never double-counted. A future field added to
#: ``SessionCheckpoint`` without updating one of the two sets fails IMMEDIATELY on import, not
#: silently at persistence time.
_ALL_FIELD_NAMES = frozenset(f.name for f in fields(SessionCheckpoint))
assert DERIVED_FIELDS | ADVISORY_FIELDS == _ALL_FIELD_NAMES, (
    "SessionCheckpoint field(s) missing an epistemic grade: "
    f"{_ALL_FIELD_NAMES - (DERIVED_FIELDS | ADVISORY_FIELDS)}"
)
assert not (DERIVED_FIELDS & ADVISORY_FIELDS), "a field cannot be both DERIVED and ADVISORY"


# ── The DERIVED / ADVISORY payload split (design D5, resolving adversarial finding F3) ─


def derived_payload(checkpoint: SessionCheckpoint) -> dict[str, Any]:
    """The ONLY dict ``checkpoint/v1`` folds into the canonical ``session_checkpoint`` fact's
    JSON ``value`` — exactly :data:`DERIVED_FIELDS`, nothing ADVISORY. Tuple fields are rendered
    as JSON-safe lists (mirroring ``control/reducers/pattern.py``'s own payload-to-JSON
    convention: canonical, sort-keys-friendly, no bespoke per-field encoding)."""
    raw = asdict(checkpoint)
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in raw.items() if k in DERIVED_FIELDS}


def advisory_payload(checkpoint: SessionCheckpoint) -> dict[str, Any]:
    """The narrative half — exactly :data:`ADVISORY_FIELDS` — NEVER placed in the canonical
    fact's payload (D5). A future ``checkpoint_narrative`` producer (out of this increment's
    scope, design §7 item 8) would persist this dict as a SEPARATE ``source_type=
    "checkpoint_narrative"`` ADVISORY record, bundled with the canonical fact only at the
    *handoff* level, never the *fact* level (the addendum's own "ride along as annotations"
    phrase, honoured at the level the design's F3 finding requires)."""
    raw = asdict(checkpoint)
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in raw.items() if k in ADVISORY_FIELDS}
