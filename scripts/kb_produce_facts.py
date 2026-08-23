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
"""

import argparse
import json
import os
import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

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
    workflow_facts_v1,
)
from agentic_dynamics.control.reducers._common import run_artifact_id, run_recency_key  # noqa: E402
from agentic_dynamics.core.paths import KB_ARTIFACT_DIR, REGISTRY_INDEX_PATH  # noqa: E402
from agentic_dynamics.experiment.experiment_spec import load_spec  # noqa: E402
from agentic_dynamics.experiment.spec_status import _spec_paths  # noqa: E402
from agentic_dynamics.knowledge import knowledge_stream as ks  # noqa: E402
from agentic_dynamics.knowledge import spec_ingestion as si  # noqa: E402
from agentic_dynamics.knowledge.record_factory import _now_iso  # noqa: E402

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


def _run_evidence(runs: list[dict]) -> tuple[EvidenceItem, ...]:
    """Build one ``EvidenceItem`` per run, identified by its content-addressed artifact id.

    CAP I0-I3 repair: the identity used to be ``f"workflow:{spec_name}"`` — spec-name-only, so
    EVERY run of the same spec collided on the same ``evidence_id`` regardless of model, phase
    values, or when it ran. ``run_artifact_id`` (``_common.py``) hashes the run's own recorded
    fields, so two distinct persisted run artifacts get distinct, durable, resolvable ids (a
    caller can look one back up via a ``{evidence_id: payload}`` index over this same sequence —
    see ``_evidence_resolver`` below), while re-deriving from the SAME artifact reproduces the
    same id byte-for-byte.
    """
    return tuple(
        EvidenceItem(
            source_type="workflow_run",
            evidence_id=f"workflow_run:{run_artifact_id(run)}",
            payload=run,
        )
        for run in runs
    )


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
    """Attach each fact's real ``fact_id`` (= the record's ``knowledge_id``), ready for the ladder."""
    return [fi.finalize_fact(fact, fi.build_fact_record(fact)) for fact in facts]


def _derive_workflow_facts(repository_id: str, revision: str, now: str) -> list:
    """Run the reduction LADDER: lower reducers → finalize → workflow_facts/v1 → records.

    ``workflow_facts/v1`` is the first reducer that consumes FACTS, not evidence. The producer
    therefore runs the lower rungs (attempt/job over the run JSONs, policy over the spec configs,
    spec_status over the index), finalizes each lower fact (so it carries a citable ``fact_id``),
    then hands the FINALIZED lower facts to ``workflow_facts_v1`` — which folds their ``fact_id``s
    into its own ``evidence_ids``. That is the backbone of the §4.5 staleness cascade.
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

    wf_inp = ReducerInput(
        scope_path=f"org:{repository_id}",
        scope_type="workflow",
        scope_id="",
        repository_id=repository_id,
        evidence=(),
        facts=tuple(_finalize(lower)),
        now=now,
        source_revision=revision,
    )
    wf_facts = workflow_facts_v1(wf_inp)
    return fi.derive_fact_records(wf_facts, registry_path=REGISTRY_INDEX_PATH)


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
    reduction LADDER over the lower reducers' finalized facts (I3). The producer resolves that
    source and hands it to the PURE reducer — the reducer does no I/O (design §4.1).

    The injected ``revision``/``now`` are the fallback ``source_revision``/clock; a properly
    stamped run JSON carries its own ``git_sha``/``ended_at``, which the reducers prefer, so
    re-derivation over the same inputs is byte-for-byte stable.
    """
    reducer_fn = get_reducer(reducer_version)
    if reducer_fn is None:
        raise SystemExit(f"unknown reducer {reducer_version!r} (registered: {sorted(REDUCERS)})")

    if reducer_version == "workflow_facts/v1":
        return _derive_workflow_facts(repository_id, revision, now)

    if reducer_version == "policy_facts/v1":
        evidence = tuple(
            EvidenceItem(source_type="spec", evidence_id=f"spec:{c.get('name') or '?'}", payload=c)
            for c in load_spec_configs()
        )
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


def emit_records(r, records: list) -> tuple[int, int]:
    """Write each durable artifact then publish its pointer event; skip already-checkpointed ids.

    Returns ``(emitted, skipped)``. Ordering mirrors ``kb_produce_sources.emit_records``: the
    artifact is written before the event lands (so the consumer can always read + verify the
    bytes the event hashes), then checkpointed.
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

    # 1. Derive fact records (run the reducer, then the registry-driven supersede decision).
    records = derive_facts(args.reducer, args.repository_id, revision, now)
    log(
        f"{args.reducer}: derived {len(records)} fact record(s) "
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
