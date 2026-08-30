"""Run an agent_task workflow (the execute phase) against a goal in a git worktree.

Usage:
    python scripts/run_workflow.py --spec workflows/repository/control_room_portal.yaml \
        --goal "Enhance the admin portal into a Control Room..." \
        --model openai/gpt-5.6-sol --workdir /tmp/pipeline/feature_admin-portal-control-plane

Writes the run ledger to ``experiments/results/workflows/<spec>/<timestamp>.json``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

# kb_produce_facts.py is a SIBLING script, not a package export — same dual-path dance as
# `_bootstrap` above: a direct `python scripts/run_workflow.py` run has `scripts/` itself on
# `sys.path[0]` (the bare `import` resolves); a test or caller that imports this file as
# `scripts.run_workflow` has the repo ROOT on `sys.path` instead (the `scripts.`-qualified
# fallback resolves). Imported here, not lazily inside `_emit_workflow_facts`, because the hook
# is default-ON (§4 of the design doc) — it is the common path, not a conditional CAP opt-in like
# `control.rules`/`control.context_compiler` below.
try:
    import kb_produce_facts  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.run_workflow — repo root is on sys.path
    from scripts import kb_produce_facts  # noqa: E402

from agentic_dynamics.control.live import LivePublisher  # noqa: E402
from agentic_dynamics.control.reducers._common import REVISION_FALLBACK  # noqa: E402
from agentic_dynamics.control.reducers._common import cell_id as _reducer_cell_id  # noqa: E402
from agentic_dynamics.control.signal_store import build_signal_store, load_results  # noqa: E402
from agentic_dynamics.control.step_routing import ModelSignals, route_step  # noqa: E402
from agentic_dynamics.experiment.experiment_spec import ExperimentSpec, load_spec  # noqa: E402
from agentic_dynamics.experiment.spec_status import refresh_spec_status  # noqa: E402
from agentic_dynamics.knowledge import knowledge_stream as ks  # noqa: E402
from agentic_dynamics.knowledge.knowledge_ingestion import _authorized_kb_write  # noqa: E402
from agentic_dynamics.knowledge.record_factory import _now_iso  # noqa: E402
from agentic_dynamics.knowledge.spec_ingestion import emit_spec_record  # noqa: E402
from agentic_dynamics.runtime.workflow_runner import cell_scope, run_workflow  # noqa: E402

#: CAP fact auto-emit (docs/designs/current/cap_fact_auto_emit_design.md §4): the disable-flag
#: env var. Deliberately the ONE default-ON flag in the FINOPS_* family (every other gate —
#: FINOPS_KB_WRITE, FINOPS_ACTUATION_ARMED — is opt-in, "1"-truthy, default OFF): the fact store
#: must stay current WITHOUT an operator remembering to run kb_produce_facts.py by hand after
#: every run. Set to the literal string "0" to disable; any other value (including unset) is ON.
FACT_AUTO_EMIT_ENV = "FINOPS_FACT_AUTO_EMIT"


def _spec_declares_routing(spec: ExperimentSpec) -> bool:
    """True when the spec activates per-step routing (mirrors ``validate_workflow_routing``).

    Routing is active when the workflow declares a ``model_pool``, any per-phase
    ``model``/``allowed_models`` selector, or a ``preferences`` block. Only then do we bother
    building the signal store; single-model specs run unchanged (cold router).
    """
    params = spec.workflow.params
    if params.get("model_pool"):
        return True
    if params.get("preferences"):
        return True
    return any(
        "model" in p or "allowed_models" in p for p in (params.get("phases") or [])
    )


def _load_signals(path: str) -> dict[str, ModelSignals]:
    """Load an explicit signals override from a JSON file: ``{model: {field: value, …}}``."""
    with open(path) as fh:
        raw = json.load(fh)
    return {m: ModelSignals.from_dict(d) for m, d in raw.items()}


#: The versioned-graph env-var family (Neo4jClient at
#: ``agentic_dynamics/knowledge/graph.py:156`` — "local dev only — override via ENV for prod").
#: URI resolution precedence: ``--change-analysis-graph`` (CLI) > ``FINOPS_NEO4J_URI`` >
#: ``FINOPS_NEO4J_URL``. Credentials come ONLY from ``FINOPS_NEO4J_USER`` /
#: ``FINOPS_NEO4J_PASSWORD`` when set — nothing secret is hard-coded here; without them the
#: client's own constructor defaults apply.
NEO4J_URI_ENV = ("FINOPS_NEO4J_URI", "FINOPS_NEO4J_URL")
NEO4J_USER_ENV = "FINOPS_NEO4J_USER"
NEO4J_PASSWORD_ENV = "FINOPS_NEO4J_PASSWORD"


def resolve_graph_uri(cli_value: str | None) -> str | None:
    """Resolve the versioned-graph URI: CLI > ``FINOPS_NEO4J_URI`` > ``FINOPS_NEO4J_URL`` > None.

    ``None`` means no graph analysis was explicitly requested anywhere — the caller then
    leaves the graph client unconstructed (delta-only facts, exactly the pre-graph behavior).
    """
    if cli_value:
        return cli_value
    for env in NEO4J_URI_ENV:
        value = os.environ.get(env)
        if value:
            return value
    return None


def _build_graph_client(uri: str) -> Any | None:
    """Construct the ``Neo4jClient`` for a resolved URI, or None when the graph is unavailable.

    A missing optional ``neo4j`` dependency, an unparseable URI, or a server unreachable at
    construction all degrade to ``None`` — the analyzer then emits delta-only facts and the
    run carries an explicit ``graph_status``, never a CLI crash. Credentials are threaded ONLY
    from ``FINOPS_NEO4J_USER`` / ``FINOPS_NEO4J_PASSWORD`` when set; otherwise the client's own
    constructor defaults apply.
    """
    try:
        from agentic_dynamics.knowledge.graph import Neo4jClient
    except Exception:  # noqa: BLE001 — optional dependency; graph-unavailable is a state
        return None
    kwargs: dict[str, str] = {"uri": uri}
    user = os.environ.get(NEO4J_USER_ENV)
    password = os.environ.get(NEO4J_PASSWORD_ENV)
    if user:
        kwargs["user"] = user
    if password:
        kwargs["password"] = password
    try:
        return Neo4jClient(**kwargs)
    except Exception:  # noqa: BLE001 — unreachable graph degrades, never crashes the CLI
        return None


def _build_change_analyzer(args: argparse.Namespace) -> tuple[Any | None, Any | None]:
    """Composition-root wiring for the phase-boundary evidence seam (design §5.7, cap_2a p1).

    Returns ``(analyzer, graph_client)``. The analyzer is built ONLY when ``--change-analysis``
    is passed (the seam opt-in); the graph client is built ONLY when the analyzer is enabled
    AND a graph URI is explicitly requested (``--change-analysis-graph`` or the
    ``FINOPS_NEO4J_URI``/``FINOPS_NEO4J_URL`` env vars). Any graph-construction failure
    degrades to ``graph_client=None`` — delta-only facts, the pre-existing fallback. Without
    ``--change-analysis`` BOTH are None and the run is byte-identical to the pre-seam behavior
    (the no-op default is preserved even when the graph env vars are set).
    """
    if not args.change_analysis:
        return None, None
    from agentic_dynamics.control.evidence_analyzer import EvidenceChangeAnalyzer

    graph_client = None
    uri = resolve_graph_uri(args.change_analysis_graph)
    if uri:
        graph_client = _build_graph_client(uri)
    return EvidenceChangeAnalyzer(
        graph_client=graph_client,
        graph_requested=bool(uri),
    ), graph_client


def main() -> None:
    ap = argparse.ArgumentParser(description="Run an agent_task workflow spec against a goal.")
    ap.add_argument("--spec", required=True, help="path to an ExperimentSpec YAML")
    ap.add_argument("--goal", required=True, help="feature/task prompt (substituted for {goal})")
    ap.add_argument("--model", required=True, help="provider/model id")
    ap.add_argument("--workdir", required=True, help="git worktree to run in")
    ap.add_argument("--backend", default=None, help="opencode | claude_cli (default: auto)")
    ap.add_argument("--thinking-effort", default="high")
    ap.add_argument("--thinking-budget-tokens", type=int, default=0)
    ap.add_argument("--output-token-limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=1800, help="per-phase timeout (s)")
    ap.add_argument("--phase-watchdog-min", type=float, default=None, metavar="MIN",
                    help="phase watchdog threshold in minutes (cap_runner_hardening p1): an "
                         "agent phase whose session transcript shows no new step for this long "
                         "is SIGTERM'd and fails with STALLED + evidence. Default "
                         "FINOPS_PHASE_WATCHDOG_MIN env, else 20; 0 disables the watchdog.")
    ap.add_argument("--no-commit", action="store_true", help="do not commit after phases")
    ap.add_argument("--resume", action="store_true",
                    help="skip phases that already have a [workflow] <phase> commit; when the "
                         "worktree has no such commits, fall back to the phases the derived "
                         "spec index (experiments/specs/index.json) shows as ok for this goal")
    ap.add_argument("--signals", default=None,
                    help="path to a JSON file mapping model id -> measured signals "
                         "(overrides the auto-built signal store)")
    ap.add_argument("--cap-snapshot", action="store_true",
                    help="CAP I4 (design §9): compile + best-effort record a route_next_job/v1 "
                         "ControlContext snapshot beside every routing decision. Read-only "
                         "measurement — nothing consumes the snapshot yet, and a snapshot "
                         "failure never affects the run. OFF by default: this is the first CAP "
                         "hook to touch a real production run + a real Redis connection.")
    ap.add_argument("--cap-shadow", action="store_true",
                    help="CAP I6 (design §9): everything --cap-snapshot does, PLUS runs the "
                         "fact-based route_next_job_v1 rule beside route_step, validates its "
                         "proposal (C1-C10), and records it as a shadow decision artifact — "
                         "never applied, never arms actuation. The actual route is always "
                         "route_step's, unchanged. Implies --cap-snapshot. OFF by default.")
    ap.add_argument("--no-fact-emit", action="store_true",
                    help="disable the CAP fact auto-emit hook (docs/designs/current/"
                         "cap_fact_auto_emit_design.md) for THIS invocation only. The hook is "
                         "default-ON — every completed run derives its own attempt/job/policy/"
                         "workflow facts and emits them, best-effort, scoped to this run's own "
                         "repository_id (cell_scope). Also controlled by the "
                         f"{FACT_AUTO_EMIT_ENV}=0 environment variable (a per-process override, "
                         "e.g. for a worker that must never write to the KB); this CLI flag "
                         "always wins when both are set.")
    ap.add_argument("--change-analysis", action="store_true",
                    help="evidence-integrity e6 seam (design §5.7, review F3): inject the "
                         "concrete EvidenceChangeAnalyzer at the composition root so every "
                         "committed phase ALSO hands its typed delta to the phase-boundary "
                         "evidence loop — code_change_facts/v2 facts + ACL-scoped executor "
                         "neighborhood recorded on the phase result. Best-effort — a failed "
                         "analysis never affects the phase. OFF by default (opt-in). Without "
                         "this flag the seam is byte-identical inert, even when "
                         "--change-analysis-graph or the FINOPS_NEO4J_* env vars are set.")
    ap.add_argument("--change-analysis-graph", default=None, metavar="URI",
                    help="cap_2a p1 (design §5.7): versioned-graph client URI for the "
                         "phase-boundary evidence loop (bolt://host:port). Resolved CLI > "
                         "FINOPS_NEO4J_URI > FINOPS_NEO4J_URL; credentials (when set) from "
                         "FINOPS_NEO4J_USER / FINOPS_NEO4J_PASSWORD, otherwise the client's "
                         "own constructor defaults. Only consulted when --change-analysis is "
                         "also passed; a missing optional dep / unparseable URI / unreachable "
                         "graph degrades to delta-only facts with an explicit graph_status "
                         "(unavailable) — never a CLI crash.")
    ap.add_argument("--orchestrator", action="store_true",
                    help="slice 2 (D-3/D-14/D-16): run each agent phase as a SIBLING cell "
                         "container with its scope config (via scripts/fleet/spawn_wrapper.py) "
                         "instead of in-process. OPT-IN — the default path is unchanged. The "
                         "orchestrator container mounts the docker socket (ro); a phase whose "
                         "scope fails validation refuses BEFORE the socket call.")
    ap.add_argument("--only-phase", default=None, metavar="NAME",
                    help="run a SINGLE phase (name) only — the sibling-cell entrypoint the "
                         "--orchestrator mode spawns for each phase. When set, the spec's phase "
                         "list is filtered to this name before the run.")
    args = ap.parse_args()

    spec = load_spec(Path(args.spec))

    # --only-phase: filter the spec's phases to the named phase (the sibling-cell path). The
    # rest of the composition root (routing/signals/etc.) is unchanged — a single-phase run is
    # a normal run whose phase list happens to have one member.
    if args.only_phase:
        phases = spec.workflow.params.get("phases") or []
        spec.workflow.params["phases"] = [
            p for p in phases if str(p.get("name", "")) == args.only_phase
        ]
        if not spec.workflow.params["phases"]:
            raise SystemExit(
                f"--only-phase {args.only_phase!r}: no such phase (have "
                f"{[p.get('name') for p in phases]})"
            )

    # --orchestrator: the sibling-spawn execution path (slice 2). Runs the phases as sibling
    # cells, each in its own scope, instead of calling run_workflow() in-process.
    if args.orchestrator:
        _run_orchestrator(spec, args)
        return

    # Signal-store wiring (docs/routing_next_steps.md item 1): when the spec declares routing
    # and no explicit --signals override was supplied, build the store from the measured
    # corpus so the router consumes real data instead of cold-starting. The explicit
    # signals/preferences kwargs on run_workflow remain the override hook.
    signals: dict[str, ModelSignals] | None = None
    if args.signals:
        signals = _load_signals(args.signals)
    elif _spec_declares_routing(spec):
        try:
            signals = build_signal_store(load_results())
        except (FileNotFoundError, json.JSONDecodeError):
            # No measured corpus available — let the router cold-start deterministically.
            signals = None

    router = route_step
    if bool(spec.workflow.params.get("control_route", False)):
        # CAP I7 seam (design §9 I7): a PER-SPEC opt-in — only a spec that explicitly sets
        # `workflow.params.control_route: true` ever has the plane's route choice applied, and
        # only when a fresh validate_decision() admits it. OFF by default; no committed spec
        # sets this field (docs/context_abstraction/implementation_notes.md's flip procedure).
        # Takes priority over --cap-shadow/--cap-snapshot: those are per-INVOCATION measurement
        # opt-ins, this is the per-SPEC apply opt-in.
        from agentic_dynamics.control.rules import make_applying_router

        router = make_applying_router(
            workload=spec.name,
            cell_id=_reducer_cell_id(spec.name, args.model),
            repository_id=cell_scope(args.workdir),
        )
    elif args.cap_shadow:
        # CAP I6 seam: a drop-in Router that ALSO runs + validates + records the fact-based
        # shadow decision (design §9 I6 row) — a superset of --cap-snapshot. Built here, at the
        # composition root, exactly where `route_step` is injected — `runtime.workflow_runner`
        # never imports `control` either way (Debt-2).
        from agentic_dynamics.control.rules import make_shadow_router

        router = make_shadow_router(
            workload=spec.name,
            cell_id=_reducer_cell_id(spec.name, args.model),
            repository_id=cell_scope(args.workdir),
        )
    elif args.cap_snapshot:
        # CAP I4 seam: a drop-in Router that also compiles + records a snapshot (design §9 I4
        # row). Built here, at the composition root, exactly where `route_step` is injected —
        # `runtime.workflow_runner` never imports `control` either way (Debt-2).
        from agentic_dynamics.control.context_compiler import make_snapshotting_router

        router = make_snapshotting_router(
            workload=spec.name,
            cell_id=_reducer_cell_id(spec.name, args.model),
            repository_id=cell_scope(args.workdir),
        )

    # Phase-boundary evidence (design §5.7 — e6 of cap_evidence_integrity, review F3): the
    # concrete ChangeAnalyzer is injected HERE, at the composition root, exactly where
    # `route_step`/`publisher_factory` are — `runtime.workflow_runner` consumes only the
    # runtime-owned protocol. Opt-in via --change-analysis (default: the seam is inert).
    # --change-analysis-graph (or FINOPS_NEO4J_URI/FINOPS_NEO4J_URL) additionally wires the
    # versioned-graph client (cap_2a p1). The returned graph_client is a live driver handle
    # and is ALWAYS closed after the run, even when run_workflow raises; a run that never
    # requested graph analysis has graph_client=None and the finally is a no-op.
    change_analyzer, graph_client = _build_change_analyzer(args)

    try:
        result = run_workflow(
            spec,
            goal=args.goal,
            model=args.model,
            workdir=args.workdir,
            backend=args.backend,
            thinking_effort=args.thinking_effort,
            thinking_budget_tokens=args.thinking_budget_tokens,
            output_token_limit=args.output_token_limit,
            timeout=args.timeout,
            commit=not args.no_commit,
            resume=args.resume,
            phase_watchdog_min=args.phase_watchdog_min,
            signals=signals,
            router=router,
            publisher_factory=LivePublisher,
            change_analyzer=change_analyzer,
        )
    finally:
        if graph_client is not None:
            with contextlib.suppress(Exception):
                graph_client.close()

    print(json.dumps(result.to_dict(), indent=2))

    out_dir = ROOT / "experiments" / "results" / "workflows" / spec.name
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"{ts}.json"
    out_path.write_text(json.dumps(result.to_dict(), indent=2))
    print(f"\nledger: {out_path}", file=sys.stderr)
    # ``getattr`` so the composition-root tests that substitute a minimal result namespace
    # (no ``awaiting`` field) keep working unchanged.
    if getattr(result, "awaiting", False):
        # cap_runner_hardening2 §Gap 3 — a designed stop, not a failure: the operator's tools
        # read "awaiting operator approval", never a bare ok/failed. Exits 0 (a designed stop).
        print(
            f"awaiting_operator_approval: phase '{getattr(result, 'awaiting_phase', '?')}' "
            f"(reason: {getattr(result, 'awaiting_reason', '?')})  cost: ${result.total_cost_usd:.4f}",
            file=sys.stderr,
        )
    else:
        print(f"cost: ${result.total_cost_usd:.4f}  ok: {result.ok}", file=sys.stderr)

    _refresh_index(spec.name)
    _emit_spec_record(spec.name, revision=result.git_sha)
    if _fact_auto_emit_enabled(args):
        _emit_workflow_facts(spec, args, result)


def _run_orchestrator(spec: ExperimentSpec, args: argparse.Namespace) -> None:
    """The orchestrator execution path (slice 2, D-3/D-14/D-16).

    Each agent phase spawns as a SIBLING cell container with its scope config, instead of
    running in-process. The sibling runs ``run_workflow.py --only-phase <name>`` (the normal
    single-phase path) inside a container whose mounts/network/env are the phase's scope —
    resolved + validated by ``scripts/fleet/spawn_wrapper.py`` BEFORE the docker socket call.

    Path mapping: the orchestrator container mounts the repo at ``/repo`` (ro) and the host
    worktree root at ``/tmp`` (rw). The sibling inherits the SAME mounts, so the spec path maps
    to ``/repo/<spec>`` and the workdir is used verbatim (the host /tmp namespace is shared).
    """
    # scripts/fleet/ is a dir, not a package — add it beside scripts/ so the wrapper imports.
    sys.path.insert(0, str(Path(__file__).resolve().parent / "fleet"))
    import spawn_wrapper  # noqa: E402

    spec_path = f"/repo/{args.spec}"
    phases = spec.workflow.params.get("phases") or []
    print(f"[orchestrator] running {len(phases)} phase(s) as sibling cells (spec {spec_path})",
          flush=True)

    failures = 0
    for phase_def in phases:
        name = str(phase_def.get("name", "?"))
        kind = str(phase_def.get("kind", "agent"))
        if kind == "test":
            print(f"[orchestrator] {name}: skipping test phase in orchestrator mode (run "
                  f"in-process or as its own cell)", flush=True)
            continue

        sibling_cmd = [
            sys.executable, "scripts/run_workflow.py",
            "--spec", spec_path,
            "--goal", args.goal,
            "--model", args.model,
            "--workdir", args.workdir,
            "--only-phase", name,
            "--timeout", str(args.timeout),
        ]
        if args.backend:
            sibling_cmd += ["--backend", args.backend]

        request = spawn_wrapper.build_phase_request(
            phase_def,
            goal=args.goal,
            workdir=args.workdir,
            model=args.model,
            spec_name=spec.name,
            command=sibling_cmd,
        )
        # build_phase_request resolves the scope; a phase with NO declared scope and no
        # authorization-table entry resolves to "" and spawn_sibling refuses it at step 2.
        print(f"[orchestrator] {name}: scope={request['scope'] or '(unauthorized)'}", flush=True)
        try:
            outcome = spawn_wrapper.spawn_sibling(request, docker="docker")
        except spawn_wrapper.SpawnValidationError as exc:
            print(f"[orchestrator] {name}: REFUSED before the socket call:\n{exc}", flush=True)
            failures += 1
            continue
        if not outcome["ok"]:
            print(f"[orchestrator] {name}: sibling exited {outcome.get('returncode')}\n"
                  f"{outcome.get('stderr', '')[-800:]}", flush=True)
            failures += 1
        else:
            print(f"[orchestrator] {name}: ok", flush=True)

    print(f"[orchestrator] done: {failures} failure(s) across {len(phases)} phase(s)", flush=True)
    if failures:
        raise SystemExit(1)


def _fact_auto_emit_enabled(args: argparse.Namespace) -> bool:
    """Resolve the fact auto-emit flag: CLI > env > default-ON (design §4's precedence table).

    ``--no-fact-emit`` always wins when passed — an explicit per-invocation CLI flag outranks the
    ambient environment, matching this file's existing ``--signals``-overrides-auto-built-store
    and ``--no-commit``-overrides-``commit=True`` precedence (``run_workflow.py``'s own argparse
    block). Absent the CLI flag, only the literal string ``"0"`` on ``FINOPS_FACT_AUTO_EMIT``
    disables — every other value, including unset, is ON (the deliberate default-ON posture break
    from the rest of the opt-in ``FINOPS_*`` family; see the module-level docstring above the
    ``FACT_AUTO_EMIT_ENV`` constant).
    """
    if args.no_fact_emit:
        return False
    return os.environ.get(FACT_AUTO_EMIT_ENV) != "0"


def _emit_workflow_facts(spec: ExperimentSpec, args: argparse.Namespace, result) -> None:
    """Derive and emit this run's own facts into the KB. Best-effort — never fails the run.

    The CAP fact-auto-emit hook (design: ``docs/designs/current/cap_fact_auto_emit_design.md``).
    Runs AFTER ``_emit_spec_record`` on purpose — the ledger is already on disk and the spec's
    lifecycle record is already current, so this call adds nothing new to the *run's* outcome; it
    can only add facts to the KB. Mirrors ``_emit_spec_record``'s two-layer posture exactly (see
    its own docstring): ``derive_run_facts`` does no I/O beyond what ``spec``/``result`` already
    hold in memory (so it essentially cannot raise on its own), and the emission half
    (``ks.connect`` / ``ks.publish_event``, which need a live Redis) is wrapped so a downed
    stream, a missing ``FINOPS_KB_WRITE`` authorization, or a corrupt registry row degrades to a
    printed warning — NEVER an exception that could change this run's exit status.

    ``repository_id=cell_scope(args.workdir)`` reuses EXACTLY the value the ``--cap-snapshot``/
    ``--cap-shadow``/``control_route`` router seams above already pass for this same ``workdir``
    (design §3): the facts this hook emits must share their ``scope_path``'s ``org:`` root with
    whatever THIS run's own routing calls query, or ``context_compiler.scope_visible``'s
    ancestor-prefix match silently excludes them.
    """
    try:
        records = kb_produce_facts.derive_run_facts(
            result,
            spec,
            repository_id=cell_scope(args.workdir),
            revision=result.git_sha or REVISION_FALLBACK,
            now=_now_iso(),
        )
        if not records:
            print("workflow facts: nothing to emit (unchanged or no phases)", file=sys.stderr)
            return
        with _authorized_kb_write():
            r = ks.connect()
            emitted, skipped = kb_produce_facts.emit_records(r, records)
        print(f"workflow facts: emitted={emitted} skipped={skipped} total={len(records)}",
              file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — progressive path, never a gate on the run
        print(f"warning: workflow fact emit failed ({exc}) — run itself unaffected", file=sys.stderr)


def _refresh_index(spec_name: str) -> None:
    """Refresh the derived spec index now that this run's ledger is on disk.

    Best-effort by construction (the ``emit_self`` pattern of
    ``workflow_runner.py:254-267``): the run has already completed and its ledger is
    already written, so an index problem — an unreadable spec YAML, a read-only
    ``experiments/specs/``, anything — must degrade to a printed warning. It may never
    fail the run or change its exit status.

    The literal env ``FINOPS_SKIP_SPEC_INDEX=1`` skips the refresh entirely — the
    cap_adaptive_2d 4-wide grid sets it on the cell subprocesses so 4 concurrent
    ``refresh_spec_status`` writers never race ``experiments/specs/index.json``; the
    campaign's post-grid phase regenerates the index once (``spec_status.py``).
    """
    if os.environ.get("FINOPS_SKIP_SPEC_INDEX") == "1":
        return
    try:
        report = refresh_spec_status(spec_name, root=ROOT)
        print(f"spec index: {report.index_path} ({report.n_specs} specs)", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — a post-run bookkeeping step, never a gate
        print(
            f"warning: spec index refresh failed ({exc}) — run itself unaffected",
            file=sys.stderr,
        )


def _emit_spec_record(spec_name: str, *, revision: str) -> None:
    """Publish this spec's lifecycle record to the knowledge base. Best-effort.

    Runs AFTER ``_refresh_index`` on purpose: the record is derived from
    ``experiments/specs/index.json``, so the index must already reflect the run that just
    finished. ``emit_spec_record`` swallows every failure internally (Redis down, the
    ``FINOPS_KB_WRITE`` guard, a missing index) and returns ``None`` — the ``emit_self``
    pattern from ``workflow_runner.py:254-267``. The extra ``try`` here is belt-and-braces
    for the import/logging path itself: nothing after a completed run may change its outcome.

    A ``None`` return is also the ordinary "lifecycle unchanged, nothing to say" case, so it
    is reported as a no-op rather than as a warning.
    """
    try:
        record = emit_spec_record(spec_name, root=ROOT, revision=revision or "workflow-run")
        if record is None:
            print("spec record: nothing to emit (unchanged or KB unreachable)", file=sys.stderr)
        else:
            print(
                f"spec record: {record.entity_id} {record.knowledge_id[:12]} "
                f"({'supersede' if record.supersedes else 'upsert'})",
                file=sys.stderr,
            )
    except Exception as exc:  # noqa: BLE001 — progressive path, never a gate
        print(f"warning: spec record emit failed ({exc}) — run itself unaffected", file=sys.stderr)


if __name__ == "__main__":
    main()
