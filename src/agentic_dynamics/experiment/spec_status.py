"""Derived spec lifecycle index — what specs exist, what is done, and when.

An agent authoring a new spec has, until now, had no way to answer "does this already
exist, and did it finish?" without reading all 60-odd YAMLs in ``experiments/specs/`` and
guessing. The run ledgers that would answer it
(``experiments/results/workflows/<spec>/<timestamp>.json``, written by
``scripts/run_workflow.py``) were write-only: nothing ever read them back.

This module joins the two sides and emits both halves of the answer:

* ``experiments/specs/index.json`` — the machine schema (one entry per spec, plus a
  ``generated_at`` stamp and a schema version), for the registry/knowledge producers and
  for the ``--resume`` fallback.
* ``experiments/specs/STATUS.md`` — the agent-facing table (one row per spec, a legend,
  a generated-at line), for a human or an LLM reading the repo.

**The index is derived, never hand-maintained.** The spec YAML's lifecycle fields are the
*seed* (what the operator asserted); the run JSONs are the *measured evidence* (what
actually happened) and win wherever both speak. Nothing here writes back into a spec YAML.

**Missing data is normal, not a failure.** ``experiments/results/workflows/`` is untracked,
so a fresh checkout has zero run ledgers; every run-derived column then renders as an
em-dash and every spec still appears in the index. A malformed run JSON is warned about and
skipped, never raised — the index must be generatable from any state of the working tree.

Design: ``code_reviews/2026-08-14_experiment-spec-and-compiler-design.md`` (the spec layer);
``experiments/specs/spec_lifecycle.yaml`` (this layer).
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agentic_dynamics.core.paths import PROJECT_ROOT
from agentic_dynamics.experiment.experiment_spec import ExperimentSpec, load_spec

# ── Constants ───────────────────────────────────────────────────

#: Repo-root-relative location of the spec corpus and of the run ledgers. Relative
#: literals (rather than absolutes) so an alternate ``root=`` — a test's ``tmp_path``, a
#: worktree — reuses the same layout without a second set of constants.
SPECS_DIR_REL = "experiments/specs"
WORKFLOW_RESULTS_DIR_REL = "experiments/results/workflows"

INDEX_FILENAME = "index.json"
STATUS_FILENAME = "STATUS.md"

#: Bumped when the shape of an ``index.json`` entry changes, so a consumer that cached an
#: older index can tell rather than mis-parse it. v2 added the ``artifact_kind`` and
#: ``repeatable`` identity columns (refactor-repair P1-4 index).
INDEX_SCHEMA_VERSION = "spec-status/v2"

#: Rendered in place of any column with no evidence behind it. An em-dash reads as
#: "nothing measured", where a ``0``/``false``/``None`` would read as a measured failure.
MISSING = "—"

#: Row ordering for ``STATUS.md``: rank by status, then by name. Runnable-now specs come
#: first because that is what an authoring agent is scanning for; live runs and the three
#: "needs attention" states (``awaiting_approval``/``failed``/``blocked``) sit just behind
#: them; completed one-shots and retired lineage sink to the bottom. Any status outside this
#: tuple sorts after all of them (defensive: the validator already restricts the vocabulary,
#: but the index must never crash on a stray).
STATUS_ORDER: tuple[str, ...] = (
    "runnable",
    "running",
    "awaiting_approval",
    "failed",
    "blocked",
    "draft",
    "completed",
    "superseded",
    "tombstoned",
)

#: How recent an *open* run (a ledger with ``started_at`` but no ``ended_at``) must be to
#: count as "currently running". Older than this, an open run is ``blocked`` — a run that
#: started and never resolved must not masquerade as live forever (review item 8 / P2).
RUNNING_WINDOW = timedelta(hours=24)

#: Timestamp format of a run-ledger filename (``20260819T142530Z.json``) — the fallback
#: when the ledger body carries no ``ended_at``/``started_at``.
_FILENAME_TS_FORMAT = "%Y%m%dT%H%M%SZ"


# ── Timestamp normalization ─────────────────────────────────────


def _now() -> datetime:
    """Current UTC time. Isolated so tests can monkeypatch a fixed clock."""
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    """Canonical ISO-8601 UTC rendering used for every timestamp this module emits."""
    return moment.astimezone(timezone.utc).isoformat()


def parse_timestamp(text: str | None) -> datetime | None:
    """Parse any timestamp shape this repo produces into an aware UTC ``datetime``.

    Three shapes reach us and they cannot be compared as strings:

    * ``2026-08-19T14:25:30.123456+00:00`` — ``workflow_runner._now()`` (ISO with offset)
    * ``2026-08-19T14:25:30Z`` — ISO with a ``Z`` suffix (``fromisoformat`` rejects this
      on Python < 3.11, hence the explicit swap)
    * ``20260819T142530Z`` — the run-ledger *filename* stem

    Returns ``None`` for anything unparseable, so a corrupt field degrades to "no
    timestamp" instead of raising in the middle of an index refresh.
    """
    if not text:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            moment = datetime.strptime(raw, _FILENAME_TS_FORMAT)
        except ValueError:
            return None
    # A naive timestamp is treated as UTC: everything in this repo is written in UTC, and
    # leaving it naive would make it uncomparable with the aware ones.
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


# ── Run ledgers (the measured evidence) ─────────────────────────


@dataclass
class RunSummary:
    """The handful of fields the index needs out of one run ledger.

    Deliberately a projection, not the whole ``WorkflowRunResult``: the index is a
    navigation aid, and keeping it small means ``index.json`` stays diffable.
    """

    path: str  # repo-relative path to the run ledger JSON
    timestamp: str  # canonical ISO-8601 UTC — when the run ended (or started)
    ok: bool | None = None
    model: str | None = None
    cost_usd: float | None = None
    git_sha: str | None = None
    #: P1 (awaiting-approval fix): True when the run ledger carries ``awaiting: true`` — the
    #: run stopped at a mechanical human checkpoint (or a resume refused past an unsatisfied
    #: one). A designed stop, never a failure: the index derives ``awaiting_approval`` for a
    #: spec whose LATEST run is awaiting, not ``failed``.
    awaiting: bool = False
    # Current-execution evidence (review item 8): a ledger with ``started_at`` but no
    # ``ended_at`` is *open* — it may still be in flight. ``started_at`` anchors the recency
    # window that separates "running now" from "blocked (started, never resolved)".
    started_at: str | None = None
    open: bool = False

    @property
    def moment(self) -> datetime | None:
        """Parsed ``timestamp``, for ordering. ``None`` sorts as "oldest"."""
        return parse_timestamp(self.timestamp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "timestamp": self.timestamp,
            "ok": self.ok,
            "model": self.model,
            "cost_usd": self.cost_usd,
            "git_sha": self.git_sha,
            "awaiting": self.awaiting,
            "started_at": self.started_at,
            "open": self.open,
        }


def summarize_run(path: Path, payload: dict[str, Any], *, root: Path) -> RunSummary:
    """Project one loaded run ledger into a :class:`RunSummary`.

    The run's time is ``ended_at`` (when the run *finished* — the honest completion
    stamp), falling back to ``started_at``, then to the filename stem. Every one of those
    can be absent in an older or truncated ledger, hence the ladder. A ledger with a
    ``started_at`` but no ``ended_at`` is marked ``open`` (review item 8) so the index can
    tell "still running" from "started and never resolved".
    """
    ended = parse_timestamp(payload.get("ended_at"))
    started = parse_timestamp(payload.get("started_at"))
    moment = ended or started or parse_timestamp(path.stem)
    cost = payload.get("total_cost_usd")
    return RunSummary(
        path=_relative_to(path, root),
        timestamp=_iso(moment) if moment else "",
        ok=payload.get("ok") if isinstance(payload.get("ok"), bool) else None,
        model=str(payload["model"]) if payload.get("model") else None,
        cost_usd=float(cost) if isinstance(cost, (int, float)) else None,
        git_sha=str(payload["git_sha"]) if payload.get("git_sha") else None,
        awaiting=payload.get("awaiting") is True,
        started_at=_iso(started) if started else None,
        open=(ended is None and started is not None),
    )


def load_runs(spec_name: str, *, results_dir: Path, root: Path) -> list[RunSummary]:
    """Load every run ledger for one spec, oldest first.

    Tolerates the whole directory being absent (untracked in a fresh checkout) and skips
    individual malformed files with a warning. The index must be generatable from any
    state of the working tree, so nothing in here raises.
    """
    spec_dir = results_dir / spec_name
    if not spec_dir.is_dir():
        return []

    runs: list[RunSummary] = []
    for path in sorted(spec_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            warnings.warn(
                f"spec_status: skipping unreadable run ledger {path}: {exc}",
                UserWarning,
                stacklevel=2,
            )
            continue
        if not isinstance(payload, dict):
            warnings.warn(
                f"spec_status: skipping non-object run ledger {path}", UserWarning, stacklevel=2
            )
            continue
        runs.append(summarize_run(path, payload, root=root))

    # Oldest first. Runs with an unparseable timestamp sort to the front so they never
    # masquerade as "latest" and shadow a real, dated run.
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    runs.sort(key=lambda r: (r.moment is not None, r.moment or epoch))
    return runs


# ── The index entry ─────────────────────────────────────────────


@dataclass
class SpecStatusEntry:
    """One spec's derived lifecycle row — the unit of both ``index.json`` and ``STATUS.md``."""

    name: str
    version: str
    status: str
    spec_path: str  # repo-relative path to the spec YAML
    #: Artifact identity (refactor-repair P1-4 index) — surfaced so STATUS.md can answer
    #: "what work remains?" per kind, not just per name. ``repeatable`` is ``None`` only for
    #: an entry that predates the backfill; post-backfill every spec carries a concrete bool.
    artifact_kind: str = ""
    repeatable: bool | None = None
    supersedes: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    completed_at: str | None = None  # authored in the YAML; the index never invents it
    last_run_at: str | None = None  # measured (max run timestamp), else the YAML's seed
    latest_ok: bool | None = None
    latest_model: str | None = None
    latest_cost_usd: float | None = None
    latest_git_sha: str | None = None
    results_pointer: str | None = None  # repo-relative path to the latest run ledger
    n_runs: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "status": self.status,
            "spec_path": self.spec_path,
            "artifact_kind": self.artifact_kind,
            "repeatable": self.repeatable,
            "supersedes": list(self.supersedes),
            "superseded_by": self.superseded_by,
            "completed_at": self.completed_at,
            "last_run_at": self.last_run_at,
            "latest_ok": self.latest_ok,
            "latest_model": self.latest_model,
            "latest_cost_usd": self.latest_cost_usd,
            "latest_git_sha": self.latest_git_sha,
            "results_pointer": self.results_pointer,
            "n_runs": self.n_runs,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SpecStatusEntry:
        """Rebuild an entry from ``index.json`` — the read path for the resume fallback."""
        return cls(
            name=d["name"],
            version=d.get("version", ""),
            status=d.get("status", ""),
            spec_path=d.get("spec_path", ""),
            artifact_kind=d.get("artifact_kind", ""),
            repeatable=d.get("repeatable") if isinstance(d.get("repeatable"), bool) else None,
            supersedes=list(d.get("supersedes") or []),
            superseded_by=d.get("superseded_by"),
            completed_at=d.get("completed_at"),
            last_run_at=d.get("last_run_at"),
            latest_ok=d.get("latest_ok"),
            latest_model=d.get("latest_model"),
            latest_cost_usd=d.get("latest_cost_usd"),
            latest_git_sha=d.get("latest_git_sha"),
            results_pointer=d.get("results_pointer"),
            n_runs=int(d.get("n_runs", 0)),
        )


def _is_currently_running(
    runs: list[RunSummary],
    *,
    now: datetime | None = None,
    window: timedelta = RUNNING_WINDOW,
) -> bool:
    """True when a run is *currently* executing — an open run whose start is recent.

    "Open" = the ledger recorded a ``started_at`` but no ``ended_at`` (the run is still in
    flight, or died without writing an end stamp). "Recent" = within ``window`` of ``now``,
    so a run that started last week and never wrote an end stamp is *blocked*, not running.
    """
    now = now or _now()
    for run in runs:
        if not run.open:
            continue
        start = parse_timestamp(run.started_at) or run.moment
        if start is not None and (now - start) <= window:
            return True
    return False


def derive_status(
    spec: ExperimentSpec,
    runs: list[RunSummary] | None = None,
    *,
    now: datetime | None = None,
    running_window: timedelta = RUNNING_WINDOW,
) -> str:
    """Resolve a spec's lifecycle status (review item 8 — current-execution evidence).

    The precedence is fixed by the spec-lifecycle design:

    1. the YAML's ``status``, when the operator authored one (an explicit ``draft`` or
       ``tombstoned`` is a claim only a human can make);
    2. otherwise ``superseded`` when ``superseded_by`` is set — a spec that names its
       replacement has, by definition, been replaced;
    3. otherwise, **per-kind**:
       * a *repeatable* spec (an experiment, or an idempotent operation) is always
         ``runnable`` — it is re-runnable by construction;
       * a *non-repeatable* workflow derives its state from the run ledgers: ``running``
         when a run is *currently* executing (an open run within ``running_window``),
         ``awaiting_approval`` when the LATEST run stopped at a mechanical human
         checkpoint (the ledger carries ``awaiting: true`` — a designed pause for the
         operator, never a failure), ``completed`` when any run succeeded,
         ``failed`` when a run recorded a definitive failure and none is running,
         ``blocked`` when runs exist but none resolved (no verdict and nothing in
         flight), and ``runnable`` when it has never been run.

    ``running`` is the one state that REQUIRES positive evidence of current execution — a
    historical failed or abandoned run never stays ``running`` indefinitely. This is the P2
    fix: "attempts but no success" is ``failed``/``blocked``, not a permanent ``running``.

    The ``awaiting_approval`` state is the P1 fix: a correctly-paused run (``ok: false`` +
    ``awaiting: true`` on the ledger — a checkpoint stop, or a resume refused past an
    unsatisfied checkpoint) must read as "waiting for the operator", NOT as ``failed``. The
    check keys the LATEST run only: an awaiting run that predates a later success (or a later
    genuine failure) is shadowed by the more recent verdict, and a pause that IS the latest
    run reads as ``awaiting_approval`` even when an earlier run succeeded (a re-run stopped
    for the operator is active work). A definitive ``ok: false`` + ``awaiting: false`` latest
    run still derives ``failed``.

    Note what is deliberately *absent*: run history never demotes a *repeatable* spec to
    ``draft``. "Never run" and "draft" are different facts, and the table shows the first
    one directly (``n_runs``/``last_run``) rather than folding it into the status column.
    """
    if spec.status:
        return spec.status
    if spec.superseded_by:
        return "superseded"
    if not spec.repeatable:
        runs = runs or []
        if _is_currently_running(runs, now=now, window=running_window):
            return "running"
        # P1: the LATEST run is awaiting operator approval — a designed pause, distinct from
        # a definitive failure. The check keys the latest run ONLY: an awaiting run that
        # predates a later success is shadowed by that later verdict (completed), while a
        # pause that is itself the latest signal reads as awaiting_approval even if an
        # earlier run succeeded (a re-run stopped for the operator IS active work).
        if runs and runs[-1].awaiting:
            return "awaiting_approval"
        if any(run.ok is True for run in runs):
            return "completed"
        if any(run.ok is False for run in runs):
            return "failed"
        if runs:
            return "blocked"
        return "runnable"
    return "runnable"


def build_entry(
    spec: ExperimentSpec, spec_path: Path, runs: list[RunSummary], *, root: Path
) -> SpecStatusEntry:
    """Join one spec with its run ledgers into an index entry.

    Seed-vs-evidence rule: where the YAML asserted ``last_run_at``/``results_pointer`` and
    a real run ledger also exists, the *measured* run wins; the YAML value survives only
    as the fallback for a spec whose runs live outside this checkout.
    """
    latest = runs[-1] if runs else None
    return SpecStatusEntry(
        name=spec.name,
        version=spec.version,
        status=derive_status(spec, runs),
        spec_path=_relative_to(spec_path, root),
        artifact_kind=spec.artifact_kind,
        repeatable=spec.repeatable,
        supersedes=list(spec.supersedes),
        superseded_by=spec.superseded_by,
        completed_at=spec.completed_at,
        last_run_at=(latest.timestamp if latest and latest.timestamp else spec.last_run_at),
        latest_ok=latest.ok if latest else None,
        latest_model=latest.model if latest else None,
        latest_cost_usd=latest.cost_usd if latest else None,
        latest_git_sha=latest.git_sha if latest else None,
        results_pointer=(latest.path if latest else spec.results_pointer),
        n_runs=len(runs),
    )


def sort_entries(entries: list[SpecStatusEntry]) -> list[SpecStatusEntry]:
    """Order rows by status rank (see :data:`STATUS_ORDER`) then by name."""

    def key(entry: SpecStatusEntry) -> tuple[int, str]:
        rank = (
            STATUS_ORDER.index(entry.status) if entry.status in STATUS_ORDER else len(STATUS_ORDER)
        )
        return (rank, entry.name)

    return sorted(entries, key=key)


def _spec_paths(root_path: Path) -> list[Path]:
    """Every committed spec YAML across the split layout (design §4).

    Genuine experiment definitions live at the top level of ``experiments/definitions/``;
    work-order specs live under ``workflows/`` (recursively). The measurement configs
    (``experiments/definitions/configs/``) and grid/sweep configs (``experiments/campaigns/``)
    are configs, not ExperimentSpecs, and are deliberately excluded.
    """
    paths = sorted((root_path / "experiments" / "definitions").glob("*.yaml"))
    paths += sorted((root_path / "workflows").rglob("*.yaml"))
    return paths


def collect_entries(*, root: Path | str = PROJECT_ROOT) -> list[SpecStatusEntry]:
    """Scan the spec corpus and the run ledgers; return sorted index entries.

    A spec YAML that fails to load (malformed, missing a required key) is warned about and
    skipped rather than aborting the scan — one broken spec must not hide the other 63.
    """
    root_path = Path(root).resolve()
    results_dir = root_path / WORKFLOW_RESULTS_DIR_REL

    entries: list[SpecStatusEntry] = []
    for spec_path in _spec_paths(root_path):
        try:
            spec = load_spec(spec_path)
        except Exception as exc:  # noqa: BLE001 — any load failure is a skip, never a crash
            warnings.warn(
                f"spec_status: skipping unloadable spec {spec_path}: {exc}",
                UserWarning,
                stacklevel=2,
            )
            continue
        runs = load_runs(spec.name, results_dir=results_dir, root=root_path)
        entries.append(build_entry(spec, spec_path, runs, root=root_path))

    return sort_entries(entries)


# ── Rendering: index.json + STATUS.md ───────────────────────────


def build_index(
    entries: list[SpecStatusEntry], *, generated_at: str | None = None
) -> dict[str, Any]:
    """Assemble the ``index.json`` document: schema version, stamp, and the entries."""
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "generated_at": generated_at or _iso(_now()),
        "n_specs": len(entries),
        "specs": [e.to_dict() for e in entries],
    }


def _fmt_bool(value: bool | None) -> str:
    """``ok``/``fail``/em-dash — never a bare ``False`` that could read as "not measured"."""
    if value is None:
        return MISSING
    return "ok" if value else "fail"


def _fmt_cost(value: float | None) -> str:
    return MISSING if value is None else f"${value:.4f}"


def _fmt_timestamp(value: str | None) -> str:
    """Shorten an ISO timestamp to ``YYYY-MM-DD HH:MM`` for the table; em-dash if absent."""
    moment = parse_timestamp(value)
    return moment.strftime("%Y-%m-%d %H:%M") if moment else MISSING


def _fmt_list(values: list[str]) -> str:
    return ", ".join(values) if values else MISSING


def _fmt_text(value: str | None) -> str:
    return value if value else MISSING


def _fmt_kind(value: str) -> str:
    """The artifact kind column — ``experiment``/``workflow``, or an em-dash when unset."""
    return value if value else MISSING


def _fmt_repeatable(value: bool | None) -> str:
    """The repeatable column — ``yes``/``no``, or an em-dash when unset (pre-backfill)."""
    if value is None:
        return MISSING
    return "yes" if value else "no"


#: The statuses an authoring agent treats as "still open" — work remaining, counted by the
#: summary line. ``awaiting_approval``/``failed``/``blocked`` are open (awaiting an operator
#: decision, a retry, or an unblock) but are not "runnable now"; the summary label below says
#: "open", not "runnable-now", for that reason.
OPEN_STATUSES = frozenset(
    {"runnable", "running", "awaiting_approval", "failed", "blocked", "draft"}
)

#: The statuses that mean "finished" — completed one-shots and retired lineage sink out of
#: the open view (refactor-repair P1-4 index).
DONE_STATUSES = frozenset({"completed", "superseded", "tombstoned"})


def render_status_md(entries: list[SpecStatusEntry], *, generated_at: str | None = None) -> str:
    """Render the agent-facing ``STATUS.md``: summary, table, legend.

    Columns are ``name | kind | repeatable | status | version | supersedes | last_run |
    ok | model | cost | n_runs`` — the ``kind``/``repeatable`` identity columns are new in
    the P1-4 index pass. A one-line summary above the table answers "what work remains?",
    and the sort order (see :data:`STATUS_ORDER`) separates the runnable-now group from the
    completed/retired group. The legend is part of the artifact rather than a doc elsewhere,
    so an agent that opens only this file still knows how to read it.
    """
    stamp = generated_at or _iso(_now())
    open_count = sum(1 for e in entries if e.status in OPEN_STATUSES)
    done = sum(1 for e in entries if e.status in DONE_STATUSES)
    lines: list[str] = [
        "# Spec status index",
        "",
        "**Generated — do not edit by hand.** Regenerate with `python scripts/spec_status.py`;",
        "`scripts/run_workflow.py` also refreshes it at the end of every run.",
        "",
        f"Generated at: `{stamp}`  ·  {len(entries)} spec(s)",
        f"**Work remaining:** {open_count} open · {done} completed/retired",
        "",
        "| name | kind | repeatable | status | version | supersedes | last_run | ok | model | cost | n_runs |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    for e in entries:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{e.name}`",
                    _fmt_kind(e.artifact_kind),
                    _fmt_repeatable(e.repeatable),
                    e.status,
                    _fmt_text(e.version),
                    _fmt_list(e.supersedes),
                    _fmt_timestamp(e.last_run_at),
                    _fmt_bool(e.latest_ok),
                    _fmt_text(e.latest_model),
                    _fmt_cost(e.latest_cost_usd),
                    str(e.n_runs),
                ]
            )
            + " |"
        )

    lines += [
        "",
        "## Legend",
        "",
        "**Status** — authored in the spec YAML's `status:` when the operator asserted one,",
        "otherwise derived: `superseded` when the spec names a `superseded_by:`; for a",
        "non-repeatable workflow, `completed` when any run succeeded, `awaiting_approval`",
        "when the latest run stopped at a mechanical human checkpoint (`awaiting: true` on",
        "the ledger — a designed pause, never a failure), `failed` when a run",
        "recorded a definitive failure, `blocked` when runs exist but none resolved, `running`",
        "when a run is currently executing (an open, recent run), `runnable` when never run;",
        "else (a repeatable spec) `runnable`.",
        "",
        "| status | meaning |",
        "|---|---|",
        "| `runnable` | never run (a non-repeatable workflow), or a repeatable spec — ready to run |",
        "| `running` | a non-repeatable workflow currently executing — an open run within the window |",
        "| `awaiting_approval` | the latest run stopped at a human checkpoint (`awaiting: true`) — the operator must approve before it continues |",
        "| `failed` | a non-repeatable workflow whose run(s) recorded a definitive failure |",
        "| `blocked` | a non-repeatable workflow with runs that started but never resolved |",
        "| `draft` | authored, not yet run to completion; not yet a claim about anything |",
        "| `completed` | a non-repeatable workflow whose run succeeded (derived from the "
        "run ledgers) |",
        "| `superseded` | a later spec took over its question (see that spec's "
        "`supersedes` column) |",
        "| `tombstoned` | retired; kept for lineage, never to be run again |",
        "",
        "**Columns**",
        "",
        "| column | derivation |",
        "|---|---|",
        "| `name` / `version` | the spec YAML's `name:` / `version:` |",
        "| `kind` | the spec YAML's `artifact_kind:` — `experiment` or `workflow` |",
        "| `repeatable` | the spec YAML's `repeatable:` — `yes` (re-runnable) or `no` (one-shot) |",
        "| `supersedes` | spec name(s) this spec replaces, from the YAML's `supersedes:` |",
        f"| `last_run` | latest run ledger's `ended_at` (UTC), over "
        f"`{WORKFLOW_RESULTS_DIR_REL}/<name>/*.json` |",
        "| `ok` | that latest run's `ok` — every phase succeeded (`ok`) or at least one "
        "failed (`fail`) |",
        "| `model` / `cost` | that latest run's `model` and `total_cost_usd` |",
        "| `n_runs` | how many run ledgers exist for the spec in this checkout |",
        "",
        f"`{MISSING}` means **no evidence**, not failure — the run-ledger directory",
        f"(`{WORKFLOW_RESULTS_DIR_REL}/`) is untracked, so a fresh checkout shows an em-dash",
        "for every run-derived column. The machine-readable form of this table, including",
        f"`results_pointer` (path to the latest run ledger), is `{INDEX_FILENAME}` beside"
        " this file.",
        "",
    ]
    return "\n".join(lines)


# ── Writing + reading the artifacts ─────────────────────────────


@dataclass
class SpecStatusReport:
    """What a refresh did — returned so callers can log it without re-reading the files."""

    index_path: Path
    status_path: Path
    n_specs: int
    entries: list[SpecStatusEntry] = field(default_factory=list)

    def entry_for(self, spec_name: str) -> SpecStatusEntry | None:
        """The refreshed entry for one spec, if that spec is in the corpus."""
        return next((e for e in self.entries if e.name == spec_name), None)


def refresh_spec_status(
    spec_name: str | None = None,
    *,
    root: Path | str = PROJECT_ROOT,
    generated_at: str | None = None,
) -> SpecStatusReport:
    """Regenerate ``index.json`` + ``STATUS.md`` from the spec corpus and run ledgers.

    ``spec_name`` is advisory: both artifacts are whole-file documents, so refreshing one
    spec's entry means rewriting them from a full rescan (64 small YAMLs — cheap enough
    that an incremental path would only add a desync failure mode). The argument is kept
    because callers want the refreshed entry for *their* spec back, which
    :meth:`SpecStatusReport.entry_for` provides; it is never a filter on what is written.
    """
    root_path = Path(root).resolve()
    specs_dir = root_path / SPECS_DIR_REL
    specs_dir.mkdir(parents=True, exist_ok=True)

    stamp = generated_at or _iso(_now())
    entries = collect_entries(root=root_path)

    index_path = specs_dir / INDEX_FILENAME
    status_path = specs_dir / STATUS_FILENAME
    index = build_index(entries, generated_at=stamp)
    index_path.write_text(json.dumps(index, indent=2) + "\n")
    status_path.write_text(render_status_md(entries, generated_at=stamp))

    report = SpecStatusReport(
        index_path=index_path, status_path=status_path, n_specs=len(entries), entries=entries
    )
    if spec_name and report.entry_for(spec_name) is None:
        # Not an error: a spec can legitimately be run from a path outside the corpus.
        warnings.warn(
            f"spec_status: refreshed index does not contain spec {spec_name!r} "
            f"(not found in {SPECS_DIR_REL}/)",
            UserWarning,
            stacklevel=2,
        )
    return report


def load_index(*, root: Path | str = PROJECT_ROOT) -> dict[str, Any]:
    """Read ``index.json`` back. Returns ``{}`` when it is absent or unreadable.

    Read-side callers (the ``--resume`` fallback) treat "no index" and "unusable index"
    identically — they fall through to their prior behaviour — so this never raises.
    """
    path = Path(root).resolve() / SPECS_DIR_REL / INDEX_FILENAME
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def index_entry(spec_name: str, *, root: Path | str = PROJECT_ROOT) -> SpecStatusEntry | None:
    """Look one spec up in the on-disk index. ``None`` when absent or unreadable."""
    for raw in load_index(root=root).get("specs", []) or []:
        if isinstance(raw, dict) and raw.get("name") == spec_name:
            try:
                return SpecStatusEntry.from_dict(raw)
            except (KeyError, TypeError, ValueError):
                return None
    return None


# ── Helpers ─────────────────────────────────────────────────────


def _relative_to(path: Path, root: Path) -> str:
    """Repo-relative POSIX path, falling back to the absolute one when outside ``root``.

    Every path the index publishes is repo-relative so ``index.json`` is identical across
    checkouts (and therefore diffable); a path that genuinely lives elsewhere is emitted
    absolute rather than mangled into a chain of ``..`` segments.
    """
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()
