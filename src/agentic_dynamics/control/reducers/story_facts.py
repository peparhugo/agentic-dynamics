"""CAP story bridge — the ``story_facts/v1`` reducer (first-class story fact bridge).

The census (``docs/designs/current/cap_fact_backfill_coverage.md`` §3) named the gap E4's
writeup (``experiments/definitions/cap_grit_strength_grid.yaml`` finding 3) made concrete: no
registered reducer consumes ``StoryResult`` artifacts, so story-cell attempts are bridged into the
fact plane only through the p3 backfill's *ledger-adaptation* — producer-side projection of story
sessions onto the ``workflow_run`` shape, fed to the UNCHANGED ``attempt_facts/v1``. ``story_facts/v1``
is that reducer: it consumes the raw ``StoryResult`` artifact directly (``source_type="story"``) and
mints one :class:`CanonicalFact` per measured per-session field, structurally analogous to
``attempt_facts/v1`` — the same evidence-identity discipline (per-session run-qualified scope,
content-addressed identity), the same null-not-zero semantics (an absent field is absent, never a
defaulted ``0``), and the same epistemic mapping (measured → ``observed``/[M],
``attempt_confidence`` → ``advisory``/[H], ``phase_test_verified`` → ``verified``/[M]).

What it adds over the p3 adaptation (all first-class, all in the reducer, none in the producer):

* **``phase_test_verified`` from the cell-level ``test_executed_success``** — the 
  *test_executed_success-analogue (story-level test outcome)* the workflow names. Story cells
  record ``test_executed_success`` cell-level only (92/227 in the census); there is no per-session
  test verdict to fabricate, so the reducer attaches the cell's independent test outcome to the
  cell's TERMINAL session attempt — the settled state of the job the suite actually verified —
  and only when the field is a real bool (``None`` stays absent: null-not-zero).
* **``attempt_tokens_in``/``attempt_tokens_out`` from the backend-reported session split** (the
  s1 instrumentation, additive to the flat ``total_tokens``) — the census's PARTIAL story rows
  become PRODUCED on re-derivation wherever a backend reported usage; a measured zero is a real
  split, a missing key is not.
* **First-class registration** — ``story_facts/v1`` is in ``REDUCERS``, so ``verify_chain`` and
  ``scripts/kb_produce_facts.py --reducer story_facts/v1`` resolve it like any other reducer.

**Design decision — attempt scope only, job facts stay with ``job_facts/v1`` (documented here
because the workflow asks for "job-level facts" and the exclusion is deliberate).** A registered
reducer's ``spec.level`` must equal the ``abstraction_level`` of every fact it emits — the
:func:`~agentic_dynamics.control.facts.verify_chain` invariant every consumer checks — and attempt
predicates declare ``abstraction_level="fact"`` while job predicates declare ``"job"``. One
registered version cannot span both without emitting facts a control path would refuse. The
workflow's job-level intent is already PRODUCED for stories: ``job_status`` /
``job_accumulated_cost_usd`` / ``job_n_phases`` / ``current_commit`` are all 227/227 via the
existing ``job_facts/v1`` path (census §3b), and re-emitting them here under a second
``reducer_version`` would hand the registry two producers for one slot. ``story_facts/v1`` is the
ATTEMPT-level bridge; the job-level story facts keep their single producer.

**Identity.** Each fact is scoped ``attempt:<session>`` under ``job:<cell>`` where ``<cell> =
wf_<story>_<condition>_<model>`` (``_common.cell_id`` — the same cell the p3 adaptation names, so a
condition-less cell lands in the story's unconditioned cell and distinct conditions stay distinct
jobs) — AND further qualified by ``run:<run_artifact_id>``. The run artifact for a session is built
by :func:`_session_run`, which replicates ``scripts/kb_produce_facts._project_story_session``'s
run-dict construction byte-for-byte, so a ``story_facts/v1`` fact occupies the SAME logical slot the
p3 adaptation derived under ``attempt_facts/v1``: emitting the bridge over the corpus therefore
SUPERSEDES the adaptation facts (same ``fact_entity_id``, new ``reducer_version``, new value → the
registry's supersede chain), never coexists with them as a conflicted second producer.

Per-run identity: two cells that happen to share story/model/condition/session numbers get distinct
run artifacts the moment any recorded field differs (a distinct ``started_at`` at minimum), and
re-derivation over the SAME artifact is byte-for-byte stable — the same content-addressed invariant
the I2 gate enforces.

Pure and deterministic (design §4.1): no I/O, no RNG; the caller resolves the story cell JSONs and
hands them in via ``ReducerInput.evidence``; the reducer only maps ``cell → facts``. ``inp.now`` is
the fallback clock for a cell with no ``completed_at``/``started_at``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from agentic_dynamics.control.facts import (
    EPISTEMIC_MAP,
    FACT_PREDICATES,
    CanonicalFact,
    EvidenceItem,
    ReducerInput,
    ReducerSpec,
    compute_fact_entity_id,
    recompute_inputs_digest,
)
from agentic_dynamics.control.reducers._common import (
    REVISION_FALLBACK,
    as_dict,
    cell_id,
    encode_value,
    run_artifact_id,
)

# ── Reducer declaration ─────────────────────────────────────────

VERSION = "story_facts/v1"

#: The eight per-session attempt predicates the reducer emits. Every name exists in
#: FACT_PREDICATES, and every one is now declared there with this reducer as a producer.
_PRODUCES = (
    "phase_status",
    "phase_commit",
    "attempt_model",
    "attempt_tokens_in",
    "attempt_tokens_out",
    "attempt_cost_usd",
    "attempt_confidence",
    "phase_test_verified",
)

STORY_FACTS_V1 = ReducerSpec(
    name="story_facts",
    version=VERSION,
    level="fact",
    scope_type="attempt",
    consumes=("story",),  # the raw StoryResult artifact (story result cell JSON)
    produces=_PRODUCES,
    determinism="pure",
)

#: The single-discriminator epistemic mapping, specialised per predicate (design §3.4 / §5) —
#: verbatim the discipline ``attempt_facts/v1`` uses. ``attempt_confidence`` is ADVISORY (a
#: self-report, never canonical); ``phase_test_verified`` is VERIFIED (the independent test_runner,
#: ``test_executed_success`` is documented "independently verified, never self-report" in
#: ``runtime/story/models.py``); everything else is OBSERVED (recorded by the system).
_OBSERVED = "observed"
_VERIFIED = "verified"
_ADVISORY = "advisory"

_EPISTEMIC_BY_PREDICATE: dict[str, str] = {
    "attempt_confidence": _ADVISORY,
    "phase_test_verified": _VERIFIED,
}


def _epistemic(predicate: str) -> str:
    """The epistemic status for a predicate: the two flagged exceptions, else ``observed``."""
    return _EPISTEMIC_BY_PREDICATE.get(predicate, _OBSERVED)


# ── Story-cell identity ─────────────────────────────────────────


def _story_cell_identity(cell: dict[str, Any]) -> tuple[str, str]:
    """The workload + model identity of one story cell, as attempt facts must see it.

    Mirrors ``scripts/kb_produce_facts._story_cell_identity``: folding the recorded condition into
    the spec name (``<story>_<condition>``) keeps distinct conditions in DISTINCT job cells — a
    clean and a bad_seed run of the same story+model must not supersede one another — while
    multiple seeds of the SAME cell share one job slot. A condition that is empty or the string
    ``"None"`` is absent, so the cell is named by the story alone (the 9 condition-less legacy
    cells land in the story's unconditioned cell).
    """
    story = str(cell.get("story_name") or "")
    condition = str(cell.get("perturbation_condition") or "")
    spec_name = f"{story}_{condition}" if condition and condition != "None" else story
    return spec_name, str(cell.get("model") or "")


def _cell_ok(cell: dict[str, Any]) -> bool:
    """The cell's own recorded success: no cell-level error AND every session exited 0.

    Mirrors ``scripts/kb_produce_facts._cell_ok``: ``summary.all_successful`` is NOT trusted alone
    (observed cells with a session timeout carry ``all_successful=True``), so success is read from
    the raw session exit codes + the cell error field.
    """
    if cell.get("error"):
        return False
    sessions = cell.get("sessions") or []
    if not isinstance(sessions, list) or not sessions:
        return False
    return all(
        (s.get("exit_code") == 0 and not s.get("error")) if isinstance(s, dict) else False
        for s in sessions
    )


def _session_run(cell: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    """The single-phase run artifact one story SESSION pins — the session's identity anchor.

    Replicates ``scripts/kb_produce_facts._project_story_session``'s run-dict construction
    byte-for-byte (documented there; kept here so a pure reducer never imports the producer), so
    :func:`~agentic_dynamics.control.reducers._common.run_artifact_id` agrees exactly and a
    ``story_facts/v1`` fact for a session occupies the same logical slot the p3 adaptation derived
    under ``attempt_facts/v1`` (the supersede-on-emission semantics, module docstring).
    """
    spec_name, model = _story_cell_identity(cell)
    number = session.get("session_number")
    phase_name = f"session{number}" if number is not None else "session"
    phase: dict[str, Any] = {"phase": phase_name, "kind": "agent"}
    exit_code = session.get("exit_code")
    phase["status"] = "ok" if exit_code == 0 and not session.get("error") else "failed"
    commit = str(session.get("commit_hash") or "")
    if commit:
        phase["commit_hash"] = commit
    if model:
        phase["model"] = model
    cost = session.get("cost_usd")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        phase["cost_usd"] = cost
    confidence = session.get("confidence")
    if confidence is not None:
        phase["confidence"] = confidence
    tokens = session.get("tokens")
    if isinstance(tokens, dict):
        # The backend-reported in/out split (additive to the flat total_tokens). Pass through
        # exactly the measured keys; the null-safe gate below then emits attempt_tokens_in/out
        # only where the backend reported a (possibly zero) value.
        split = {"in": tokens.get("in"), "out": tokens.get("out")}
        if split["in"] is not None or split["out"] is not None:
            phase["tokens"] = split
    return {
        "spec_name": spec_name,
        "spec_id": f"{spec_name}@story",
        "model": model,
        "git_sha": commit,
        "started_at": str(cell.get("started_at") or ""),
        "ended_at": str(cell.get("completed_at") or ""),
        "total_cost_usd": (cell.get("summary") or {}).get("total_cost"),
        "ok": _cell_ok(cell),
        "phases": [phase],
    }


# ── Fact construction ───────────────────────────────────────────


def _fact(
    cell: dict[str, Any],
    session: dict[str, Any],
    phase_name: str,
    scope_id: str,
    inp: ReducerInput,
    predicate: str,
    value: str,
    evidence_id: str,
) -> CanonicalFact:
    """Build one attempt-scoped fact for ``predicate`` (design §10's scope hierarchy).

    Mirrors ``attempt_facts._fact`` exactly: ``epistemic_status`` is derived INSIDE here from the
    predicate (a call site can never disagree with the predicate's declared epistemology), and
    ``evidence_id`` is the caller's ``EvidenceItem.evidence_id`` for this cell — cited verbatim.
    """
    spec = FACT_PREDICATES[predicate]
    epistemic_status = _epistemic(predicate)
    authority, evidence_class = EPISTEMIC_MAP[epistemic_status]
    spec_name, model = _story_cell_identity(cell)
    cell_slug = cell_id(spec_name, model)
    run_id = run_artifact_id(_session_run(cell, session))
    observed_at = str(cell.get("completed_at") or cell.get("started_at") or inp.now)
    fact = CanonicalFact(
        fact_entity_id=compute_fact_entity_id(
            repository_id=inp.repository_id,
            scope_type="attempt",
            scope_id=scope_id,  # run-qualified: "<cell>:<session>:<run_artifact_id>"
            predicate=predicate,
            subject_type="attempt",
            subject_id=phase_name,
        ),
        fact_id="",  # finalized at persistence — the record's knowledge_id IS the fact_id
        subject_type="attempt",
        subject_id=phase_name,
        predicate=predicate,
        value=value,
        value_type=spec.value_type,
        unit=spec.unit,
        scope_type="attempt",
        scope_id=scope_id,
        scope_path=(
            f"org:{inp.repository_id}/workload:{spec_name}/job:{cell_slug}"
            f"/attempt:{phase_name}/run:{run_id}"
        ),
        abstraction_level=spec.abstraction_level,
        epistemic_status=epistemic_status,
        authority=authority,
        evidence_class=evidence_class,
        observed_at=observed_at,
        valid_from=observed_at,
        valid_to=None,
        expires_at=None,
        reducer="story_facts",
        reducer_version=VERSION,
        evidence_ids=(evidence_id,) if evidence_id else (),
        inputs_digest="",  # back-filled below from evidence_ids + reducer_version
        supersedes=None,  # the producer links a predecessor via the registry, not the reducer
        source_revision=str(session.get("commit_hash") or REVISION_FALLBACK),
        repository_id=inp.repository_id,
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


# ── Per-session derivation ──────────────────────────────────────


def _facts_for_session(
    cell: dict[str, Any],
    session: dict[str, Any],
    inp: ReducerInput,
    evidence_id: str,
    *,
    is_terminal: bool,
) -> list[CanonicalFact]:
    """Emit the facts one story session pins, honouring measured-or-absent semantics."""
    number = session.get("session_number")
    phase_name = f"session{number}" if number is not None else "session"
    if not phase_name:
        return []
    spec_name, model = _story_cell_identity(cell)
    cell_slug = cell_id(spec_name, model)
    run_id = run_artifact_id(_session_run(cell, session))
    scope_id = f"{cell_slug}:{phase_name}:{run_id}"

    def fact(predicate: str, value: str) -> CanonicalFact:
        return _fact(cell, session, phase_name, scope_id, inp, predicate, value, evidence_id)

    facts: list[CanonicalFact] = []
    status = "ok" if session.get("exit_code") == 0 and not session.get("error") else "failed"
    facts.append(fact("phase_status", encode_value(status, "enum")))
    commit = str(session.get("commit_hash") or "")
    if commit:
        facts.append(fact("phase_commit", encode_value(commit, "str")))
    if model:
        facts.append(fact("attempt_model", encode_value(model, "str")))
    tokens = session.get("tokens")
    if isinstance(tokens, dict):
        # Null-safe: a measured ZERO token count is a real measurement, not an absent one — only a
        # missing/None key means "not measured" (the CAP I0-I3 repair's null-safety fix).
        tokens_in = tokens.get("in")
        if tokens_in is not None:
            facts.append(fact("attempt_tokens_in", encode_value(tokens_in, "int")))
        tokens_out = tokens.get("out")
        if tokens_out is not None:
            facts.append(fact("attempt_tokens_out", encode_value(tokens_out, "int")))
    cost = session.get("cost_usd")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        facts.append(fact("attempt_cost_usd", encode_value(cost, "usd")))
    confidence = session.get("confidence")
    if confidence is not None:
        facts.append(fact("attempt_confidence", encode_value(confidence, "float")))
    # The cell-level test outcome (the test_executed_success-analogue) attaches to the TERMINAL
    # session only — the cell's settled state the independent suite actually verified. A bool is a
    # real measurement; None (the 135/227 un-verified cells) stays absent, never a fabricated
    # "false" (null-not-zero). Module docstring documents the convention.
    if is_terminal and isinstance(cell.get("test_executed_success"), bool):
        facts.append(
            fact("phase_test_verified", encode_value(cell.get("test_executed_success"), "bool"))
        )
    return facts


# ── The reducer (pure) ──────────────────────────────────────────


def story_facts_v1(inp: ReducerInput) -> list[CanonicalFact]:
    """Emit per-session attempt facts for every StoryResult cell in ``inp.evidence``.

    Pure and total: every addressable cell (a story name + model) yields its per-session facts; an
    unaddressable cell or a non-dict payload is skipped, never crashed on. Deterministic: the same
    ``ReducerInput`` yields byte-identical facts in input order.
    """
    facts: list[CanonicalFact] = []
    for item in inp.evidence:
        if not isinstance(item, EvidenceItem):
            continue
        cell = as_dict(item.payload)
        if cell is None:
            continue
        spec_name, model = _story_cell_identity(cell)
        if not spec_name or not model:
            continue  # no cell identity -> not addressable -> no facts
        sessions = cell.get("sessions") or []
        if not isinstance(sessions, list):
            continue
        live = [s for s in sessions if isinstance(s, dict)]
        for index, session in enumerate(live):
            facts.extend(
                _facts_for_session(
                    cell,
                    session,
                    inp,
                    item.evidence_id,
                    is_terminal=index == len(live) - 1,
                )
            )
    return facts
