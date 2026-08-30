"""Batch producer for the fact plane — derive canonical facts and emit pointer events.

This is the *facts* producer (CAP I1–I2, design §4.3 / §9): it runs a registered reducer over
its evidence source and persists the resulting
:class:`~agentic_dynamics.control.facts.CanonicalFact` objects through the EXISTING knowledge
pipe — ``build_fact_record`` → ``record_to_artifact`` → ``record_to_event`` → ``publish_event`` —
onto ``kb:v1:changes`` (DB 2 on 6380). It is the sibling of ``scripts/kb_produce_sources.py``
(which emits code/quality/policy/spec records) and shares its idempotence + isolation contracts
verbatim.

    python scripts/kb_produce_facts.py --reducer spec_status/v1 --dry-run     # I1: spec index
    python scripts/kb_produce_facts.py --reducer attempt_facts/v1 --dry-run   # I2: run JSONs
    python scripts/kb_produce_facts.py --reducer job_facts/v1 --limit 5       # I2: run JSONs

Each reducer names its own evidence source: ``spec_status/v1`` reads the generated
``experiments/specs/index.json`` (I1); ``attempt_facts/v1`` / ``job_facts/v1`` read the typed
workflow run JSONs (``experiments/results/workflows/**/*.json``, the
``WorkflowRunResult.to_dict()`` shape — I2). The producer resolves that source and hands it to
the pure reducer; the reducer itself does no I/O (design §4.1).

Like the ``spec`` source, a fact record can emit a ``supersede`` (rather than ``upsert``) event:
when ``registry_index.jsonl`` already holds a fact for the same ``fact_entity_id`` (the stable
slot ``<scope>/<subject>/<predicate>``) with a *different* value, the new record links its
predecessor via ``supersedes``, which is what lets ``scripts/generate_manifest.py`` derive
``lifecycle_state`` ``current`` vs ``superseded`` (design §9 I1's gate). Operation and ``reason``
are derived from the record (``fact_ingestion.fact_event``), never passed alongside it.

Idempotence (identical to ``kb_produce_sources.py``): ``knowledge_id`` is the idempotence key.
The producer checks the checkpoint hash (``CHECKPOINT_KEY`` on DB 2) and dedupes in-process; only
a never-seen ``knowledge_id`` is published, then checkpointed. The durable per-record artifact is
written to ``experiments/results/kb/<knowledge_id>.json`` BEFORE the pointer event lands.

Isolation (load-bearing): this producer touches only ``127.0.0.1:FINOPS_REDIS_PORT`` (default
6380) DB 2 — never 6379 (the story sandbox) nor DB 1 (the framework queue).

``derive_run_facts`` (below ``_derive_workflow_facts``) is a SECOND, narrower entry point: the
scoped, per-run derivation the workflow-completion auto-emit hook calls
(``scripts/run_workflow.py:_emit_workflow_facts``, design:
``docs/architecture/current/cap_fact_auto_emit_design.md``). It runs the SAME reducers and the SAME
``fact_ingestion`` glue this CLI's ``main()`` does, but over evidence built from ONE already-loaded
run + spec rather than a corpus-wide filesystem scan — no new transport, no reducer changes.
"""

import argparse
import json
import os
import subprocess
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

# scripts/ → repo root → src, so the local package wins over any installed one (matches the
# bootstrap in worker.py / kb_worker.py / kb_produce.py).
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.control import fact_ingestion as fi  # noqa: E402
from agentic_dynamics.control.facts import EvidenceItem, ReducerInput  # noqa: E402
from agentic_dynamics.control.reducers import (  # noqa: E402
    REDUCERS,
    attempt_facts_v1,
    get_reducer,
    job_facts_v1,
    policy_facts_v1,
    spec_status_v1,
    story_facts_v1,
    workflow_facts_v1,
)
from agentic_dynamics.control.reducers._common import run_artifact_id, run_recency_key  # noqa: E402
from agentic_dynamics.core.paths import KB_ARTIFACT_DIR, REGISTRY_INDEX_PATH  # noqa: E402
from agentic_dynamics.experiment.experiment_spec import ExperimentSpec, load_spec  # noqa: E402
from agentic_dynamics.experiment.spec_status import _spec_paths  # noqa: E402
from agentic_dynamics.knowledge import knowledge_stream as ks  # noqa: E402
from agentic_dynamics.knowledge import spec_ingestion as si  # noqa: E402
from agentic_dynamics.knowledge.record_factory import _now_iso  # noqa: E402
from agentic_dynamics.reporting import canonical_corpus as cc  # noqa: E402

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))

#: Repo root, anchored to the script location so flags may be omitted regardless of cwd.
REPO_ROOT = Path(__file__).resolve().parent.parent

#: How many sample records ``--dry-run`` prints (a preview, not the whole batch).
SAMPLE_COUNT = 5


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][kb-produce-facts] {msg}", flush=True)


def git_head_sha() -> str:
    """Return the repo's HEAD sha (the injected ``revision``), or ``""`` when unavailable."""
    r = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip() if r.returncode == 0 else ""


# ── Derivation: run one registered reducer → facts → records ────

#: The reducers that consume the typed workflow run JSONs (I2) rather than the spec index (I1).
RUN_REDUCERS = frozenset({"attempt_facts/v1", "job_facts/v1"})


def load_run_jsons() -> list[dict]:
    """Load every typed workflow run JSON (``experiments/results/workflows/**/*.json``).

    Skips unreadable/non-object files — a run ledger that fails to parse must not hide the rest.
    Each returned dict is the ``WorkflowRunResult.to_dict()`` shape ``scripts/run_workflow.py:108``
    writes (spec_name / model / git_sha / ended_at / phases[] / total_cost_usd / ok / …).

    Returned oldest-recorded-run-first (CAP I0-I3 repair), keyed by each run's OWN
    ``ended_at``/``started_at`` — never the filesystem traversal order and never a wall clock —
    so a batch covering several runs of one cell processes deterministically and
    ``fact_ingestion.derive_fact_records``'s in-batch chaining lands on the most-recently-recorded
    run's value as current (job facts are current-per-cell summaries, see ``job_facts.py``). Ties
    (e.g. two runs with no timestamps) break on the run's own canonical JSON for full
    determinism.
    """
    results_dir = REPO_ROOT / "experiments" / "results" / "workflows"
    runs: list[dict] = []
    if not results_dir.is_dir():
        return runs
    for path in sorted(results_dir.rglob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            runs.append(payload)
    runs.sort(key=lambda r: (run_recency_key(r), json.dumps(r, sort_keys=True, default=str)))
    return runs


def load_spec_configs() -> list[dict]:
    """Load the declared L5 config from every spec YAML.

    Returns one projection per spec — ``name`` + the three L5 fields (``budget_usd`` /
    ``max_attempts`` / ``model_pool``) — the shape ``policy_facts/v1`` consumes. Uses the same
    path scan as ``spec_status.collect_entries`` (``_spec_paths``) so the fact plane's view of
    "the spec corpus" can never drift from the lifecycle index's.
    """
    configs: list[dict] = []
    for path in _spec_paths(REPO_ROOT):
        try:
            spec = load_spec(path)
        except Exception:  # noqa: BLE001 — one broken spec must not hide the rest
            continue
        pool = spec.workflow.params.get("model_pool") or spec.workflow.params.get("allowed_models")
        configs.append(
            {
                "name": spec.name,
                "budget_usd": spec.stop.budget_usd,
                "max_attempts": spec.stop.max_attempts,
                "model_pool": list(pool) if isinstance(pool, (list, tuple)) else pool,
            }
        )
    return configs


def _is_failed_before_call(phase: dict) -> bool:
    """True when a phase is a STRUCTURAL zero-cost phase: it failed before any model call.

    CAP fact backfill F1 (the m2 hazard): a phase that fails before any model call (e.g. an auth
    failure) records ``cost_usd=0.0`` with an all-zero ``tokens`` block. That ``0.0`` is a
    structural zero (the model was never called), not a measured zero — deriving it as a real cost
    lets a never-executed run read as "within budget" (``projected_budget_overrun=0.0``). The
    discriminant is exact: agent-kind + a failure status + zero cost + zero tokens in/out/total.
    Test-kind phases are never "failed-before-call" — they run pytest (no model call by design),
    so their ``0.0`` is a genuine measurement.
    """
    if phase.get("kind") not in (None, "agent"):
        return False
    if phase.get("status") not in ("failed", "error", "timeout", "blocked"):
        return False
    if phase.get("cost_usd") not in (0, 0.0):
        return False
    tokens = phase.get("tokens") or {}
    if isinstance(tokens, dict):
        return not any(tokens.get(k) for k in ("in", "out", "total"))
    return True


def _sanitize_run(run: dict) -> dict:
    """Return a copy of a workflow run with F1 structural-zero costs recorded as ``None``.

    Re-derivation stays byte-stable: the sanitizer is a pure, deterministic function of the raw
    artifact, and it is applied only to the evidence PAYLOAD — ``run_artifact_id`` (the identity
    cited in ``evidence_ids``) is computed over the RAW artifact, never the sanitized copy, so an
    already-cited run keeps its exact identity.
    """
    run = dict(run)
    phases = run.get("phases")
    if not isinstance(phases, list) or not phases:
        return run
    new_phases: list = []
    before_call = 0
    for phase in phases:
        if not isinstance(phase, dict):
            new_phases.append(phase)
            continue
        if _is_failed_before_call(phase):
            phase = {**phase, "cost_usd": None}  # uncaptured, not a measured zero
            before_call += 1
        new_phases.append(phase)
    run["phases"] = new_phases
    if before_call == len(new_phases) and run.get("total_cost_usd") in (0, 0.0):
        run["total_cost_usd"] = None  # the whole run never executed — cost is unmeasured
    return run


def _run_evidence(runs: list[dict]) -> tuple[EvidenceItem, ...]:
    """Build one ``EvidenceItem`` per DISTINCT run, identified by its content-addressed artifact id.

    CAP I0-I3 repair: the identity used to be ``f"workflow:{spec_name}"`` — spec-name-only, so
    EVERY run of the same spec collided on the same ``evidence_id`` regardless of model, phase
    values, or when it ran. ``run_artifact_id`` (``_common.py``) hashes the run's own recorded
    fields, so two distinct persisted run artifacts get distinct, durable, resolvable ids (a
    caller can look one back up via a ``{evidence_id: payload}`` index over this same sequence —
    see ``_evidence_resolver`` below), while re-deriving from the SAME artifact reproduces the
    same id byte-for-byte.

    **F1 sanitization (CAP fact backfill):** the PAYLOAD handed to the reducers is the sanitized
    copy (``_sanitize_run`` — failed-before-call costs become ``None``), while the ``evidence_id``
    is computed over the RAW artifact (identity is a property of the persisted bytes, and an
    already-cited run keeps its exact id). See ``_sanitize_run`` for the F1 m2-hazard rationale.

    **Duplicate-evidence guard (CAP I0-I3 adversarial repair, attack vector "duplicate evidence"):**
    two ON-DISK FILES can carry byte-identical content (a copied/duplicated artifact, or a replay
    that re-wrote the same result under a new timestamp-named file) — ``load_run_jsons`` would
    legitimately hand back two separate dict entries for them. Two ``EvidenceItem``s with the same
    ``evidence_id`` are, by this module's own identity contract, THE SAME EVIDENCE — handing both
    to a reducer would double-count every phase/job fact they mint (a cell with one completed
    phase would read ``workflow_phases_completed=2``). This is the one place that resolves raw
    evidence, so it is the one place that must deduplicate it — ``derive_fact_records`` already
    protects the FINAL persisted records from a duplicate (the "byte-identical first version
    already registered" branch), but it never sees ``workflow_facts_v1``'s in-memory phase counts,
    which read the raw reducer output directly. Kept the first occurrence deterministically (input
    order is already recency-sorted by ``load_run_jsons``) — which occurrence survives is
    immaterial since, by definition of the identity scheme, their content is identical.
    """
    seen: set[str] = set()
    items: list[EvidenceItem] = []
    for run in runs:
        rid = run_artifact_id(run)
        if rid in seen:
            continue
        seen.add(rid)
        items.append(
            EvidenceItem(
                source_type="workflow_run",
                evidence_id=f"workflow_run:{rid}",
                payload=_sanitize_run(run),
            )
        )
    return tuple(items)


def evidence_resolver(items: tuple[EvidenceItem, ...]) -> Callable[[str], object | None]:
    """Return a ``verify_chain``-compatible resolver over an already-resolved evidence sequence.

    Not a new store: ``ReducerInput.evidence`` is already fully resolved in-process (design
    §4.1's "the caller resolves inputs"), so this is just a dict lookup over what is already in
    memory — the same posture as the reducers themselves. Lets a caller (or a test) confirm that
    every ``evidence_id`` an I2 fact cites actually resolves, per CAP I0-I3's "raw-evidence facts
    cite durable, resolvable input identity" invariant.
    """
    index = {item.evidence_id: item.payload for item in items}
    return index.get


def _finalize(facts: list) -> list:
    """Attach each fact's real ``fact_id`` (the record's ``knowledge_id``), ready for the ladder."""
    return [fi.finalize_fact(fact, fi.build_fact_record(fact)) for fact in facts]


def _finalize_to_registered(lower: list, identity_out: dict[int, str]) -> list:
    """Finalize the lower facts with the ids they are ACTUALLY registered under.

    ``workflow_facts_v1`` cites the lower facts' ``fact_id``s (the staleness-cascade backbone), and
    the citation must resolve to a REGISTERED row. ``derive_fact_records``' ``identity_out`` maps
    each fact to its registered knowledge_id — its first-version record, its linked record, or (for
    a fact that converged to an earlier run's identical value) the head it converged to. The naive
    unlinked ``build_fact_record`` id names a knowledge_id that is NEVER registered in the converged
    case, which minted dangling workflow-fact citations for every multi-run cell.
    """
    finalized: list = []
    for fact in lower:
        rid = identity_out.get(id(fact))
        if rid is None:  # a fact the batch did not touch (defensive — identity_out is total)
            rid = fi.build_fact_record(fact).knowledge_id
        record = replace(fi.build_fact_record(fact), knowledge_id=rid)
        finalized.append(fi.finalize_fact(fact, record))
    return finalized


def _derive_workflow_facts(repository_id: str, revision: str, now: str) -> list:
    """Run the reduction LADDER: lower reducers → finalize → workflow_facts/v1 → records.

    ``workflow_facts/v1`` is the first reducer that consumes FACTS, not evidence. The producer
    therefore runs the lower rungs (attempt/job over the run JSONs, policy over the spec configs,
    spec_status over the index), registers the lower facts (so the citations ``workflow_facts/v1``
    folds into its ``evidence_ids`` resolve against REGISTERED rows), then finalizes them with
    their registered ids and hands them up — that is the backbone of the §4.5 staleness cascade.
    """
    runs = load_run_jsons()
    run_inp = ReducerInput(
        scope_path=f"org:{repository_id}",
        scope_type="workload",
        scope_id="",
        repository_id=repository_id,
        evidence=_run_evidence(runs),
        facts=(),
        now=now,
        source_revision=revision,
    )
    lower: list = attempt_facts_v1(run_inp) + job_facts_v1(run_inp)

    policy_inp = ReducerInput(
        scope_path=f"org:{repository_id}",
        scope_type="workload",
        scope_id="",
        repository_id=repository_id,
        evidence=tuple(
            EvidenceItem(source_type="spec", evidence_id=f"spec:{c.get('name') or '?'}", payload=c)
            for c in load_spec_configs()
        ),
        facts=(),
        now=now,
        source_revision=revision,
    )
    lower += policy_facts_v1(policy_inp)

    spec_inp = ReducerInput(
        scope_path=f"org:{repository_id}",
        scope_type="workload",
        scope_id="",
        repository_id=repository_id,
        evidence=tuple(
            EvidenceItem(source_type="spec", evidence_id=f"spec:{e.name}", payload=e)
            for e in si.load_index_entries(root=REPO_ROOT)
        ),
        facts=(),
        now=now,
        source_revision=revision,
    )
    lower += spec_status_v1(spec_inp)

    identity_out: dict[int, str] = {}
    lower_records = fi.derive_fact_records(lower, registry_path=REGISTRY_INDEX_PATH, identity_out=identity_out)
    wf_inp = ReducerInput(
        scope_path=f"org:{repository_id}",
        scope_type="workflow",
        scope_id="",
        repository_id=repository_id,
        evidence=(),
        facts=tuple(_finalize_to_registered(lower, identity_out)),
        now=now,
        source_revision=revision,
    )
    wf_facts = workflow_facts_v1(wf_inp)
    wf_records = fi.derive_fact_records(wf_facts, registry_path=REGISTRY_INDEX_PATH)
    return lower_records + wf_records


# ── Scoped, per-run derivation: the workflow-completion auto-emit hook ──
#
# CAP fact-auto-emit (docs/architecture/current/cap_fact_auto_emit_design.md). `_derive_workflow_facts`
# above is the CORPUS-WIDE batch job: it rglobs every run JSON ever written and every spec YAML in
# the repo. That is the right shape for an operator's periodic `--reducer workflow_facts/v1` sweep;
# it is the wrong shape for a hook firing on every single workflow completion (O(corpus) I/O paid
# per run, and — if pointed at a per-cell `repository_id` — permanent registry fragmentation of the
# corpus-wide `policy_facts`/`spec_status` slots, design §2). `derive_run_facts` below reuses the
# EXACT SAME reducer functions and the EXACT SAME `fact_ingestion` glue, but is handed evidence
# built ONLY from the run/spec the caller already holds in memory — no filesystem re-scan at all.


def _policy_evidence_for(spec: ExperimentSpec) -> tuple[EvidenceItem, ...]:
    """Build ONE ``policy_facts/v1`` evidence item for an already-loaded spec (no directory scan).

    Mirrors ``load_spec_configs()``'s per-spec projection (``name`` / ``budget_usd`` /
    ``max_attempts`` / ``model_pool``) field-for-field, applied to the ONE ``ExperimentSpec``
    ``scripts/run_workflow.py`` already parsed for this run — the scoped, per-run sibling of the
    corpus-wide ``load_spec_configs()`` used by the manual ``--reducer policy_facts/v1`` sweep.
    """
    pool = spec.workflow.params.get("model_pool") or spec.workflow.params.get("allowed_models")
    config = {
        "name": spec.name,
        "budget_usd": spec.stop.budget_usd,
        "max_attempts": spec.stop.max_attempts,
        "model_pool": list(pool) if isinstance(pool, (list, tuple)) else pool,
    }
    return (EvidenceItem(source_type="spec", evidence_id=f"spec:{spec.name}", payload=config),)


def _registered_observed_at(entity_id: str, *, registry_path: Path) -> str | None:
    """Return the CURRENT (non-superseded) registry head's own ``observed_at`` for ``entity_id``.

    ``None`` when there is no head yet. Mirrors ``spec_ingestion.registry_head``'s tolerant,
    two-pass parsing exactly (missing/unreadable file -> ``None``; a malformed line is skipped,
    not fatal — a producer must never be blocked by a damaged index) but surfaces the head row's
    ``observed_at`` instead of its lifecycle-fingerprint ``reason``: ``RegistryHead`` (the value
    object ``registry_head`` returns) does not carry ``observed_at``, and extending it would touch
    ``spec_ingestion.py``, which serves BOTH the spec and fact planes — a shared-schema change is
    out of scope for a hook-local guard (hard rule 5: no reducer/registry-schema changes). This
    stays entirely local to ``kb_produce_facts.py``, reading the same raw file the shared helper
    reads, so it costs nothing new: adversarial finding f3-2 (see the design doc's log) needs it
    to detect out-of-order run completion BEFORE deciding whether to derive at all.
    """
    path = Path(registry_path)
    try:
        raw_lines = path.read_text().splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    order: list[str] = []
    lines: dict[str, dict] = {}
    superseded: set[str] = set()
    for raw in raw_lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue  # a truncated line must not hide the rest of the history
        if not isinstance(row, dict) or row.get("entity_id") != entity_id:
            continue
        kid = row.get("knowledge_id")
        if not kid:
            continue
        if row.get("supersedes"):
            superseded.add(str(row["supersedes"]))
        if row.get("lifecycle_state") == "superseded":
            superseded.add(str(kid))
        if kid not in lines:
            order.append(str(kid))
        lines[str(kid)] = row  # latest line for an id wins
    for kid in reversed(order):
        if kid not in superseded:
            return lines[kid].get("observed_at")
    return None


def derive_run_facts(
    result: object,
    spec: ExperimentSpec,
    *,
    repository_id: str,
    revision: str,
    now: str,
) -> list:
    """Derive fact records for ONE just-finished workflow run — the auto-emit hook's derivation.

    Runs every run-scoped reducer over evidence built ONLY from ``result`` (the run that just
    finished) and ``spec`` (the one spec the caller already parsed): ``attempt_facts/v1`` and
    ``job_facts/v1`` over the run's own evidence, ``policy_facts/v1`` over the spec's own declared
    budget/attempts ceiling, then ``workflow_facts/v1`` over the FINALIZED lower facts (the same
    ladder ``_derive_workflow_facts`` runs — see its docstring for why the lower rungs must be
    finalized before ``workflow_facts_v1`` can cite their ``fact_id``s in its own ``evidence_ids``).

    Unlike ``_derive_workflow_facts`` (which registers ONLY the top-of-ladder ``workflow_facts_v1``
    output), this function registers the RAW attempt/job/policy facts too — a failed run's own
    ``phase_status``/``job_status`` facts land in the registry as their own citable records, not
    merely folded into the workflow-level aggregate. This is a deliberate widening within the
    SAME unchanged reducers and the SAME ``fact_ingestion.derive_fact_records`` glue (no reducer
    changes, no new transport — hard rule 5): one combined call lets the convergence guard and
    in-batch chaining (``fact_ingestion.py``) do the deduplication across all four fact families at
    once, exactly as they already do for a mixed batch.

    ``spec_status/v1`` (I1, the corpus-wide spec lifecycle index) is deliberately NOT run here — it
    has no per-run input to give and stays the manual/scheduled batch job's responsibility.

    **Out-of-order-completion guard (adversarial finding f3-2, `f3_adversarial_verify`).** Unlike
    the batch job — which loads every run for a cell in ONE call and lets
    ``fact_ingestion.derive_fact_records``'s in-batch chaining sort them by ``observed_at`` before
    deciding a winner — this function is called ONCE PER RUN, from a SEPARATE process invocation
    each time. Two runs of the SAME cell that finish out of chronological order (a slow worker, a
    delayed retry, or two workers racing) each see only their OWN run's facts; there is no shared
    in-process list to sort. Concretely reproduced: a fast run T2 (``ended_at`` 00:20) registers
    first; a slow run T1 (``ended_at`` 00:05, STARTED earlier but finished LATER in wall-clock
    terms) is then processed — with nothing guarding it, ``derive_fact_records`` would silently
    supersede T2's correct ``job_status``/``job_accumulated_cost_usd`` with T1's stale values,
    because it only ever compares CONTENT (has the value changed?), never RECENCY (is this
    observation older than what's already registered?) across separate calls. Guarded below by
    checking the incoming run's own ``job_status`` ``observed_at`` against the currently-registered
    head's ``observed_at`` for that SAME cell/entity (``_registered_observed_at``, a hook-local
    helper — no reducer or registry-schema change) and skipping the ENTIRE derivation (not just the
    job facts) for a run that is strictly older than what is already registered: every fact this
    function derives from ONE run shares that run's provenance, so a stale run must not be allowed
    to set ANY of the cell's "current" state, not merely the job-level rungs.

    No I/O beyond what ``result``/``spec`` already hold in memory — save the ONE registry read the
    guard above performs, which reuses the same tolerant, never-blocking read shape
    ``registry_head`` already has. Safe to call from a hot completion path.
    """
    run = result.to_dict() if hasattr(result, "to_dict") else result
    workload_scope = f"org:{repository_id}/workload:{spec.name}"

    run_inp = ReducerInput(
        scope_path=workload_scope,
        scope_type="workload",
        scope_id="",
        repository_id=repository_id,
        evidence=_run_evidence([run]),
        facts=(),
        now=now,
        source_revision=revision,
    )
    attempt = attempt_facts_v1(run_inp)
    job = job_facts_v1(run_inp)

    job_status = next((f for f in job if f.predicate == "job_status"), None)
    if job_status is not None:
        registered_at = _registered_observed_at(
            job_status.fact_entity_id, registry_path=REGISTRY_INDEX_PATH
        )
        if registered_at is not None and job_status.observed_at < registered_at:
            return []  # this run is older than the cell's already-registered state — drop it

    policy_inp = ReducerInput(
        scope_path=workload_scope,
        scope_type="workload",
        scope_id="",
        repository_id=repository_id,
        evidence=_policy_evidence_for(spec),
        facts=(),
        now=now,
        source_revision=revision,
    )
    policy = policy_facts_v1(policy_inp)

    lower = attempt + job + policy
    identity_out: dict[int, str] = {}
    lower_records = fi.derive_fact_records(lower, registry_path=REGISTRY_INDEX_PATH, identity_out=identity_out)
    wf_inp = ReducerInput(
        scope_path=workload_scope,
        scope_type="workflow",
        scope_id="",
        repository_id=repository_id,
        evidence=(),
        facts=tuple(_finalize_to_registered(lower, identity_out)),
        now=now,
        source_revision=revision,
    )
    wf_facts = workflow_facts_v1(wf_inp)
    wf_records = fi.derive_fact_records(wf_facts, registry_path=REGISTRY_INDEX_PATH)
    return lower_records + wf_records


def derive_facts(
    reducer_version: str,
    repository_id: str,
    revision: str,
    now: str,
) -> list:
    """Run the named reducer over its evidence source; return the persistable fact records.

    Each reducer names its own source: ``spec_status/v1`` reads the generated spec index (I1);
    ``attempt_facts/v1`` / ``job_facts/v1`` read the typed workflow run JSONs (I2);
    ``policy_facts/v1`` reads the declared L5 config (I3); ``workflow_facts/v1`` runs the
    reduction LADDER over the lower reducers' finalized facts (I3); ``pattern/v1`` (I9) reads
    the canonical-corpus ``finding`` table (the reducer's one input door — design §3.3). The
    producer resolves that source and hands it to the PURE reducer — the reducer does no I/O
    (design §4.1).

    The injected ``revision``/``now`` are the fallback ``source_revision``/clock; a properly
    stamped run JSON carries its own ``git_sha``/``ended_at``, which the reducers prefer, so
    re-derivation over the same inputs is byte-for-byte stable.
    """
    reducer_fn = get_reducer(reducer_version)
    if reducer_fn is None:
        raise SystemExit(f"unknown reducer {reducer_version!r} (registered: {sorted(REDUCERS)})")

    if reducer_version == "workflow_facts/v1":
        return _derive_workflow_facts(repository_id, revision, now)

    if reducer_version == "pattern/v1":
        evidence = _pattern_finding_evidence()
    elif reducer_version == "policy_facts/v1":
        evidence = tuple(
            EvidenceItem(source_type="spec", evidence_id=f"spec:{c.get('name') or '?'}", payload=c)
            for c in load_spec_configs()
        )
    elif reducer_version == "story_facts/v1":
        # The first-class story bridge: the RAW StoryResult artifact (not the projection).
        evidence = _story_cell_evidence(load_story_cells())
    elif reducer_version in RUN_REDUCERS:
        evidence = _run_evidence(load_run_jsons())
    else:  # spec_status/v1
        evidence = tuple(
            EvidenceItem(source_type="spec", evidence_id=f"spec:{e.name}", payload=e)
            for e in si.load_index_entries(root=REPO_ROOT)
        )

    inp = ReducerInput(
        scope_path=f"org:{repository_id}",
        scope_type="workload",
        scope_id="",  # the whole corpus — the reducer emits per-spec / per-run / per-phase facts
        repository_id=repository_id,
        evidence=evidence,
        facts=(),
        now=now,
        source_revision=revision,
    )
    facts = reducer_fn(inp)
    return fi.derive_fact_records(facts, registry_path=REGISTRY_INDEX_PATH)


# ── Additive corpus families: story cells + summary entries (CAP fact backfill, p3) ──
#
# The workflow-run reducers above are UNCHANGED. This section projects the two additional corpus
# families — story result cells (``experiments/results/stories/*.json``) and the retired summary
# corpus (``experiments/results/_results_summary.json``) — onto the run-artifact shape
# ``attempt_facts/v1`` and ``job_facts/v1`` already consume, so facts derive through the EXISTING
# reducer vocabulary with ZERO reducer diffs. The three evidence families mirror the
# ``workflow_run`` pattern (content-addressed ``run_artifact_id`` per artifact, dedup, per-run
# identity):
#
#   * ``story_session``   — one run per story SESSION (a single-phase run); consumed by
#                           ``attempt_facts/v1`` → per-session attempt facts.
#   * ``story_result``    — one run per story CELL (job-level aggregates + the session list);
#                           consumed by ``job_facts/v1`` → per-cell job facts.
#   * ``summary_attempt`` — one run per summary ENTRY (a single-phase run); consumed by
#                           ``attempt_facts/v1`` → per-entry attempt facts.
#
# Absent fields stay absent (null-not-zero): a story session records no in/out token split, so
# ``attempt_tokens_in/out`` are never emitted for it; a summary entry records no status/commit/
# confidence, so ``phase_status``/``phase_commit``/``attempt_confidence`` are never emitted for
# it. Nothing is fabricated, and the summary family is deliberately fed to ``attempt_facts/v1``
# ONLY — ``job_facts/v1`` would force a ``job_status`` ("failed") for an entry that records no
# ``ok``, which is exactly the fabrication null-not-zero forbids.

#: Relative paths of the two additional families (monkeypatchable in hermetic tests via
#: ``REPO_ROOT``, exactly like ``load_run_jsons``' workflows path).
STORY_RESULTS_DIR_REL = "experiments/results/stories"
SUMMARY_RESULTS_FILE_REL = "experiments/results/_results_summary.json"


def load_story_cells() -> list[dict]:
    """Load every story result cell JSON (``experiments/results/stories/*.json``).

    Mirrors ``load_run_jsons``'s tolerance: unreadable/non-object files are skipped so one broken
    cell cannot hide the rest. Each returned dict is the ``StoryResult.to_dict()`` shape
    (story_name / model / perturbation_condition / summary / sessions[] / ...).
    """
    results_dir = REPO_ROOT / STORY_RESULTS_DIR_REL
    cells: list[dict] = []
    if not results_dir.is_dir():
        return cells
    for path in sorted(results_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            cells.append(payload)
    return cells


def load_summary_entries() -> list[dict]:
    """Load the summary corpus (``experiments/results/_results_summary.json``'s ``entries``)."""
    path = REPO_ROOT / SUMMARY_RESULTS_FILE_REL
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return []
    return [e for e in entries if isinstance(e, dict)]


def _story_cell_identity(cell: dict) -> tuple[str, str]:
    """The workload + model identity of one story cell, as attempt/job facts must see it.

    The workflow cell is ``wf_<spec_name>_<model>`` (``_common.cell_id``). Story cells are
    (story x model x condition): folding the recorded condition into ``spec_name``
    (``<story>_<condition>``) keeps distinct conditions in DISTINCT job cells — a clean and a
    bad_seed run of the same story+model must not supersede one another's current-per-cell job
    facts — while multiple seeds of the SAME cell share one job slot (job facts are
    current-per-cell: the intended supersession semantics, exactly like repeated workflow runs).
    A condition that is empty or the string ``"None"`` is absent, so the cell is named by the
    story alone (the 9 condition-less legacy cells land in the story's unconditioned cell).
    """
    story = str(cell.get("story_name") or "")
    condition = str(cell.get("perturbation_condition") or "")
    spec_name = f"{story}_{condition}" if condition and condition != "None" else story
    return spec_name, str(cell.get("model") or "")


def _cell_ok(cell: dict) -> bool:
    """The cell's own recorded success: no cell-level error AND every session exited 0.

    ``summary.all_successful`` is NOT trusted alone — observed cells with a session timeout
    (``error`` non-empty) carry ``all_successful=True``, so success is read from the raw session
    exit codes + the cell error field, never from the summary's boolean.
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


def _project_story_session(cell: dict, session: dict) -> dict:
    """Project ONE story session onto the run-artifact shape ``attempt_facts/v1`` consumes.

    The session is a single-phase run whose ``run_artifact_id`` hashes the session's own recorded
    fields plus the cell identity — distinct per session (per-run identity), byte-stable across
    re-derivation. Fields the session does not record (in/out token split, cache hit rate,
    per-session test result) are simply absent.
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
        # exactly the measured keys; ``attempt_facts/v1``'s null-safe gate then emits
        # attempt_tokens_in/out only where the backend reported a (possibly zero) value.
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


def _project_story_result(cell: dict) -> dict:
    """Project ONE story cell onto the run-artifact shape ``job_facts/v1`` consumes.

    Carries the cell's aggregates (total cost, ``ok``, current commit = the LAST session's commit)
    plus the full session list (``job_n_phases`` = session count). Its ``run_artifact_id`` hashes
    the whole cell, so two seeds of the same cell are distinct runs whose job facts supersede
    oldest-first (current-per-cell), exactly like repeated workflow runs.
    """
    spec_name, model = _story_cell_identity(cell)
    sessions = [s for s in (cell.get("sessions") or []) if isinstance(s, dict)]
    current_commit = ""
    for s in reversed(sessions):
        commit = str(s.get("commit_hash") or "")
        if commit:
            current_commit = commit
            break
    return {
        "spec_name": spec_name,
        "spec_id": f"{spec_name}@story",
        "model": model,
        "git_sha": current_commit,
        "started_at": str(cell.get("started_at") or ""),
        "ended_at": str(cell.get("completed_at") or ""),
        "total_cost_usd": (cell.get("summary") or {}).get("total_cost"),
        "ok": _cell_ok(cell),
        "phases": [
            {
                "phase": (
                    f"session{s.get('session_number')}" if s.get("session_number") is not None
                    else "session"
                ),
                "kind": "agent",
                "status": "ok" if s.get("exit_code") == 0 and not s.get("error") else "failed",
                "commit_hash": str(s.get("commit_hash") or ""),
                "model": model,
            }
            for s in sessions
        ],
    }


def _project_summary_attempt(entry: dict) -> dict:
    """Project ONE summary entry onto the run-artifact shape ``attempt_facts/v1`` consumes.

    Each summary entry IS one perturbation trial (one model run), so it maps to a single-attempt
    run. ``attempt_model``/``attempt_cost_usd`` come from every entry; ``attempt_tokens_in/out``
    only from the valid entries that record ``tokens_input``/``tokens_output`` (absent elsewhere).
    ``phase_status``/``phase_commit``/``attempt_confidence`` are never emitted — the entry records
    no status/commit/confidence, and a status must not be fabricated.
    """
    spec_name = str(entry.get("experiment") or entry.get("worktree_name") or "summary")
    model = str(entry.get("model") or "")
    phase: dict[str, Any] = {
        "phase": str(entry.get("worktree_name") or entry.get("experiment") or "run"),
        "kind": "agent",
        "status": "",  # no recorded status — phase_status stays absent (null-not-zero)
        "model": model,
    }
    commit = str(entry.get("commit_hash") or "")
    if commit:
        phase["commit_hash"] = commit
    cost = entry.get("cost")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        phase["cost_usd"] = cost
    tokens: dict[str, int] = {}
    tokens_in = entry.get("tokens_input")
    if isinstance(tokens_in, (int, float)) and not isinstance(tokens_in, bool):
        tokens["in"] = int(tokens_in)
    tokens_out = entry.get("tokens_output")
    if isinstance(tokens_out, (int, float)) and not isinstance(tokens_out, bool):
        tokens["out"] = int(tokens_out)
    if tokens:
        phase["tokens"] = tokens
    confidence = entry.get("confidence")
    if confidence is not None:
        phase["confidence"] = confidence
    return {
        "spec_name": spec_name,
        "spec_id": f"{spec_name}@summary",
        "model": model,
        "git_sha": commit,
        "started_at": "",
        "ended_at": "",
        "total_cost_usd": cost,
        "phases": [phase],
    }


def _dedup_evidence(
    projects: list[dict], source_type: str
) -> tuple[EvidenceItem, ...]:
    """Mirror ``_run_evidence``'s content-addressed dedup for one projected artifact family.

    Two on-disk files carrying byte-identical content (a copied/duplicated artifact) collapse to
    ONE evidence item — the same duplicate-evidence guard ``_run_evidence`` enforces, at the same
    single place where raw evidence is resolved.
    """
    seen: set[str] = set()
    items: list[EvidenceItem] = []
    for payload in projects:
        rid = run_artifact_id(payload)
        if rid in seen:
            continue
        seen.add(rid)
        items.append(
            EvidenceItem(
                source_type=source_type,
                evidence_id=f"{source_type}:{rid}",
                payload=payload,
            )
        )
    return tuple(items)


def _story_session_evidence(cells: list[dict]) -> tuple[EvidenceItem, ...]:
    """One ``story_session`` evidence item per distinct story SESSION (single-phase run)."""
    return _dedup_evidence(
        [
            _project_story_session(c, s)
            for c in cells
            for s in (c.get("sessions") or [])
            if isinstance(s, dict)
        ],
        "story_session",
    )


def _story_cell_evidence(cells: list[dict]) -> tuple[EvidenceItem, ...]:
    """One ``story`` evidence item per distinct story CELL — the RAW StoryResult artifact.

    The evidence family ``story_facts/v1`` consumes (the first-class bridge, replacing the
    projection above for that reducer's path): one item per cell, payload = the cell dict as it
    sits on disk, content-addressed ``evidence_id`` (``story:<run_artifact_id(cell)>``). The
    reducer reads the sessions itself; no producer-side projection.
    """
    return _dedup_evidence(cells, "story")


def _story_result_evidence(cells: list[dict]) -> tuple[EvidenceItem, ...]:
    """One ``story_result`` evidence item per distinct story CELL (job-level run)."""
    return _dedup_evidence([_project_story_result(c) for c in cells], "story_result")


def _summary_attempt_evidence(entries: list[dict]) -> tuple[EvidenceItem, ...]:
    """One ``summary_attempt`` evidence item per distinct summary ENTRY (single-phase run)."""
    return _dedup_evidence([_project_summary_attempt(e) for e in entries], "summary_attempt")


def _pattern_finding_evidence() -> tuple[EvidenceItem, ...]:
    """One ``EvidenceItem`` per canonical ``finding`` row — the ``pattern/v1`` input door.

    The I9 reducer (CAP addendum I9, ``control/reducers/pattern.py``) consumes ONLY ``finding``
    evidence (design §3.3 — the canonical-corpus table that carries the structured
    ``test_executed_success`` / ``perturbation_class`` / ``_experiment`` fields a pattern needs).
    This mirrors the reducer's own integration test (``tests/test_context_plane_pattern.py``),
    which builds its ``ReducerInput`` from ``canonical_corpus.load_canonical_tables("finding")``
    the same way — the ONE input door a publication lab may use, never a directory glob. An
    empty/unresolved finding table yields an empty evidence tuple, and the reducer's coverage
    invariant (empty slice -> NO fact) does the rest; nothing here fabricates support.
    """
    tables = cc.load_canonical_tables("finding")
    return tuple(
        EvidenceItem(
            source_type="finding",
            evidence_id=str(row.get("_registry", {}).get("knowledge_id") or ""),
            payload=row,
        )
        for row in tables.findings
    )


def _family_input(
    repository_id: str,
    revision: str,
    now: str,
    evidence: tuple[EvidenceItem, ...],
) -> ReducerInput:
    """Build the workload-scoped ``ReducerInput`` the reducers expect for one evidence family."""
    return ReducerInput(
        scope_path=f"org:{repository_id}",
        scope_type="workload",
        scope_id="",
        repository_id=repository_id,
        evidence=evidence,
        facts=(),
        now=now,
        source_revision=revision,
    )


def _story_facts(repository_id: str, revision: str, now: str) -> list:
    """The raw story facts (attempt over ``story_session`` + job over ``story_result``)."""
    cells = load_story_cells()
    session_facts = attempt_facts_v1(
        _family_input(repository_id, revision, now, _story_session_evidence(cells))
    )
    result_facts = job_facts_v1(
        _family_input(repository_id, revision, now, _story_result_evidence(cells))
    )
    return session_facts + result_facts


def _summary_facts(repository_id: str, revision: str, now: str) -> list:
    """The raw summary facts (attempt over ``summary_attempt`` only)."""
    entries = load_summary_entries()
    return attempt_facts_v1(
        _family_input(repository_id, revision, now, _summary_attempt_evidence(entries))
    )


def derive_story_facts(repository_id: str, revision: str, now: str) -> list:
    """Derive the story corpus's fact records: per-session attempts + per-cell jobs."""
    return fi.derive_fact_records(_story_facts(repository_id, revision, now),
                                  registry_path=REGISTRY_INDEX_PATH)


def derive_story_facts_v1(repository_id: str, revision: str, now: str) -> list:
    """Derive the story corpus's FIRST-CLASS attempt facts via ``story_facts/v1``.

    The p3 ``derive_story_facts`` projection above (attempt over ``story_session`` + job over
    ``story_result``) is UNCHANGED; this is the new reducer's path — raw ``StoryResult`` cells →
    ``story_facts/v1`` → per-session attempt facts. Job-level story facts stay with ``job_facts/v1``
    (see the reducer's module docstring for the single-level rationale). Supersedes the projection's
    per-session facts on emission (same logical slot, new reducer_version).
    """
    return fi.derive_fact_records(
        story_facts_v1(
            _family_input(
                repository_id,
                revision,
                now,
                _story_cell_evidence(load_story_cells()),
            )
        ),
        registry_path=REGISTRY_INDEX_PATH,
    )


def derive_summary_facts(repository_id: str, revision: str, now: str) -> list:
    """Derive the summary corpus's fact records: per-entry attempts."""
    return fi.derive_fact_records(_summary_facts(repository_id, revision, now),
                                  registry_path=REGISTRY_INDEX_PATH)


def derive_corpus_facts(repository_id: str, revision: str, now: str) -> list:
    """Derive fact records for the ENTIRE corpus in ONE batch (the backfill's derivation).

    Runs the full workflow reduction LADDER over the run ledgers (attempt + job + policy +
    spec_status lower rungs finalized, then ``workflow_facts/v1``), PLUS the story and summary
    families — all through one ``derive_fact_records`` call so in-batch chaining (per-entity
    pending-head threading, oldest-first) is cross-family. Every reducer here is the unchanged
    registered one; this function only assembles evidence + glue (hard rule 5: zero reducer diffs).
    """
    runs = load_run_jsons()
    lower = attempt_facts_v1(_family_input(repository_id, revision, now, _run_evidence(runs)))
    lower += job_facts_v1(_family_input(repository_id, revision, now, _run_evidence(runs)))
    policy_inp = _family_input(
        repository_id,
        revision,
        now,
        tuple(
            EvidenceItem(source_type="spec", evidence_id=f"spec:{c.get('name') or '?'}", payload=c)
            for c in load_spec_configs()
        ),
    )
    lower += policy_facts_v1(policy_inp)
    spec_inp = _family_input(
        repository_id,
        revision,
        now,
        tuple(
            EvidenceItem(source_type="spec", evidence_id=f"spec:{e.name}", payload=e)
            for e in si.load_index_entries(root=REPO_ROOT)
        ),
    )
    lower += spec_status_v1(spec_inp)
    identity_out: dict[int, str] = {}
    lower_records = fi.derive_fact_records(lower, registry_path=REGISTRY_INDEX_PATH, identity_out=identity_out)
    wf_inp = ReducerInput(
        scope_path=f"org:{repository_id}",
        scope_type="workflow",
        scope_id="",
        repository_id=repository_id,
        evidence=(),
        facts=tuple(_finalize_to_registered(lower, identity_out)),
        now=now,
        source_revision=revision,
    )
    wf_facts = workflow_facts_v1(wf_inp)
    wf_records = fi.derive_fact_records(wf_facts, registry_path=REGISTRY_INDEX_PATH)
    all_facts = lower_records + wf_records + derive_story_facts(
        repository_id, revision, now
    ) + derive_summary_facts(repository_id, revision, now)
    return all_facts


# ── Emission (identical logic to kb_produce_sources.py) ─────────


def plan_emissions(
    records: list, *, limit: int = 0, known_ids: set[str] | frozenset[str] | None = None
) -> list:
    """Cap by ``limit`` then drop already-emitted ids (pure, no Redis)."""
    if limit and limit > 0:
        records = records[:limit]
    seen: set[str] = set(known_ids or ())
    plan: list = []
    for record in records:
        if record.knowledge_id in seen:
            continue
        seen.add(record.knowledge_id)
        plan.append(record)
    return plan


def load_checkpoint_ids(r) -> set[str]:
    """Return the already-checkpointed ``knowledge_id``s (the idempotence keys)."""
    return set(r.hkeys(ks.CHECKPOINT_KEY))


def build_event(record):
    """Build the pointer event for one fact record (operation + reason derived inside)."""
    return fi.fact_event(record)


def _materialize_registry_row(record) -> None:
    """F2 fix (CAP fact backfill): append the record's registry line(s) at EMIT time.

    The ``kb-registry-v1`` consumer is the canonical registry writer, but it only runs when a
    worker is up — artifacts were being written without registry rows (the F2 materialization
    stall: artifacts outnumbering registry rows). Materializing the row in the emit path removes
    the dependency on a live consumer for THIS producer's emission: every emitted artifact is
    registry-visible immediately, so the backfill's own artifact count == its registry row count.
    The line shape mirrors ``kb_worker.py``'s ``kb-registry-v1`` handler field-for-field
    (append-only, operation-derived ``lifecycle_state``, the ``supersede`` predecessor line);
    a later consumer pass appends byte-identical duplicate lines, which
    ``generate_manifest.py``'s compaction folds away (latest-per-entity).
    """
    operation = fi.fact_operation(record)
    reason = fi.fact_reason(record)
    lifecycle = "current" if operation in ("upsert", "supersede") else "tombstoned"
    line = {
        "knowledge_id": record.knowledge_id,
        "entity_id": record.entity_id,
        "source_type": record.source_type,
        "logical_locator": record.logical_locator,
        "source_uri": record.source_uri,
        "lifecycle_state": lifecycle,
        "observed_at": record.observed_at,
        "indexed_at": record.indexed_at,
        "supersedes": record.supersedes,
        "causes": record.causes,
        "reason": reason,
    }
    REGISTRY_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_INDEX_PATH, "a") as f:
        f.write(json.dumps(line) + "\n")
    if operation == "supersede" and record.supersedes:
        predecessor_line = {
            "knowledge_id": record.supersedes,
            "entity_id": record.entity_id,
            "lifecycle_state": "superseded",
            "valid_to": record.valid_from,
            "indexed_at": record.indexed_at,
        }
        with open(REGISTRY_INDEX_PATH, "a") as f:
            f.write(json.dumps(predecessor_line) + "\n")


def emit_records(r, records: list) -> tuple[int, int]:
    """Write each durable artifact then publish its pointer event; skip already-checkpointed ids.

    Returns ``(emitted, skipped)``. Ordering mirrors ``kb_produce_sources.emit_records``: the
    artifact is written before the event lands (so the consumer can always read + verify the
    bytes the event hashes), then checkpointed. The F2 registry-row materialization
    (``_materialize_registry_row``) runs after the checkpoint so a re-run skips both the event
    and the row.
    """
    emitted = 0
    skipped = 0
    for record in records:
        if r.hget(ks.CHECKPOINT_KEY, record.knowledge_id) is not None:
            skipped += 1
            continue
        from agentic_dynamics.knowledge.knowledge_ingestion import record_to_artifact

        artifact = record_to_artifact(record)
        KB_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        (KB_ARTIFACT_DIR / f"{record.knowledge_id}.json").write_bytes(artifact)
        ks.publish_event(r, build_event(record), source_type=record.source_type)
        r.hset(ks.CHECKPOINT_KEY, record.knowledge_id, record.indexed_at)
        _materialize_registry_row(record)
        emitted += 1
    return emitted, skipped


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Derive canonical facts from a registered reducer and emit pointer events"
    )
    parser.add_argument(
        "--reducer",
        default="spec_status/v1",
        choices=tuple(REDUCERS),
        help="reducer version to run (default: spec_status/v1)",
    )
    parser.add_argument(
        "--corpus",
        choices=("story", "summary", "all"),
        default=None,
        help=(
            "derive facts for the additive corpus families instead of --reducer: 'story' "
            "(per-session attempt + per-cell job facts from stories/*.json), 'summary' "
            "(per-entry attempt facts from _results_summary.json), or 'all' (the entire "
            "corpus: workflow ladder + story + summary in one batch)"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report the would-emit counts and samples, touching nothing",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="cap the number of records emitted (0 = no cap)",
    )
    parser.add_argument(
        "--repository-id",
        default="agentic-dynamics",
        help="repository identity folded into entity_id",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="git HEAD sha stamped as source_revision (default: rev-parse HEAD)",
    )
    args = parser.parse_args(argv)

    revision = args.revision or git_head_sha()
    now = _now_iso()

    # 1. Derive fact records (run the reducer / corpus family, then the registry-driven
    #    supersede decision).
    if args.corpus == "story":
        records = derive_story_facts(args.repository_id, revision, now)
    elif args.corpus == "summary":
        records = derive_summary_facts(args.repository_id, revision, now)
    elif args.corpus == "all":
        records = derive_corpus_facts(args.repository_id, revision, now)
    else:
        records = derive_facts(args.reducer, args.repository_id, revision, now)
    source_label = args.corpus or args.reducer
    log(
        f"{source_label}: derived {len(records)} fact record(s) "
        f"(revision={revision[:12]}, repository-id={args.repository_id!r})"
    )

    # 2. Preview / emit. Dry-run reports the honest would-emit count (derived minus already
    #    checkpointed); a downed Redis degrades to the raw derived count.
    known_ids: set[str] = set()
    if args.dry_run:
        try:
            known_ids = load_checkpoint_ids(ks.connect(host=REDIS_HOST, port=REDIS_PORT))
        except Exception:
            known_ids = set()

    plan = plan_emissions(records, limit=args.limit, known_ids=known_ids)

    if args.dry_run:
        log(f"dry-run: would emit {len(plan)} fact record(s) (limit={args.limit or 'none'})")
        for record in plan[:SAMPLE_COUNT]:
            op = fi.fact_operation(record)
            log(f"  {record.knowledge_id[:12]}  [fact/{op}]  {record.logical_locator}")
        return

    # 3. Emit — fail fast on connection. The producer is an authorized writer: satisfy
    #    publish_event's write guard (FINOPS_KB_WRITE) for the whole run.
    os.environ["FINOPS_KB_WRITE"] = "1"
    r = ks.connect(host=REDIS_HOST, port=REDIS_PORT)
    emitted, skipped = emit_records(r, plan)
    log(f"emitted={emitted} skipped={skipped} (already checkpointed) total={len(plan)}")


if __name__ == "__main__":
    main()
