"""Tests for the derived spec lifecycle index (``instrument.spec_status``).

Everything here runs against a synthetic repo built in ``tmp_path`` — an ``experiments/definitions/``
of fixture YAMLs plus a ``experiments/results/workflows/<name>/*.json`` of fixture run
ledgers — so the assertions are exact rather than "whatever the real corpus happens to
contain today". The one exception is the final test, which scans the real checkout to prove
the whole committed corpus indexes without an exception.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentic_dynamics.experiment.experiment_spec import ExperimentSpec, Factor, Workflow
pytestmark = pytest.mark.fast

from agentic_dynamics.experiment.spec_status import (
    INDEX_SCHEMA_VERSION,
    MISSING,
    STATUS_ORDER,
    RunSummary,
    SpecStatusEntry,
    build_index,
    collect_entries,
    derive_status,
    index_entry,
    load_index,
    load_runs,
    parse_timestamp,
    refresh_spec_status,
    render_status_md,
    sort_entries,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── Fixture repo ────────────────────────────────────────────────


def _spec_yaml(name: str, *, version: str = "0.1", **lifecycle: object) -> str:
    """Render a minimal but valid spec YAML, plus whatever lifecycle keys were passed."""
    lines = [
        f"name: {name}",
        f"question: does {name} work?",
        f'version: "{version}"',
        "workflow:",
        "  kind: agent_task",
        "  params: {language: python}",
        "factors:",
        "  - {name: model, levels: [anthropic/claude-opus-5]}",
        "design: factorial",
    ]
    for key, value in lifecycle.items():
        lines.append(f"{key}: {json.dumps(value)}")
    return "\n".join(lines) + "\n"


def _write_run(root: Path, spec: str, stem: str, **payload: object) -> Path:
    """Write one fixture run ledger under ``experiments/results/workflows/<spec>/``.

    The first parameter is named ``spec`` rather than ``spec_name`` on purpose: ledgers
    carry a ``spec_name`` field, and a same-named positional would swallow it.
    """
    run_dir = root / "experiments" / "results" / "workflows" / spec
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / f"{stem}.json"
    path.write_text(json.dumps(payload, indent=2))
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A synthetic repo: four specs covering every status path, with mixed run history.

    * ``alpha_v1``  — explicitly superseded by ``alpha_v2``; one old run.
    * ``alpha_v2``  — supersedes ``alpha_v1``; two runs (the later one is the "latest").
    * ``beta_draft``— authored ``status: draft``; never run.
    * ``gamma``     — no lifecycle keys at all (the shape of all 63 committed specs).
    """
    specs = tmp_path / "experiments" / "definitions"
    specs.mkdir(parents=True)

    (specs / "alpha_v1.yaml").write_text(
        _spec_yaml("alpha_v1", version="0.1", superseded_by="alpha_v2")
    )
    (specs / "alpha_v2.yaml").write_text(
        _spec_yaml("alpha_v2", version="0.2", supersedes=["alpha_v1"])
    )
    (specs / "beta_draft.yaml").write_text(_spec_yaml("beta_draft", status="draft"))
    (specs / "gamma.yaml").write_text(_spec_yaml("gamma", version="1.0"))

    _write_run(
        tmp_path,
        "alpha_v1",
        "20260810T090000Z",
        spec_name="alpha_v1",
        model="deepseek/deepseek-v4-pro",
        ok=False,
        total_cost_usd=0.5,
        git_sha="aaa1111",
        started_at="2026-08-10T08:00:00+00:00",
        ended_at="2026-08-10T09:00:00+00:00",
        phases=[{"phase": "scope", "status": "failed"}],
    )
    _write_run(
        tmp_path,
        "alpha_v2",
        "20260812T120000Z",
        spec_name="alpha_v2",
        model="anthropic/claude-opus-5",
        ok=True,
        total_cost_usd=1.25,
        git_sha="bbb2222",
        started_at="2026-08-12T11:00:00+00:00",
        ended_at="2026-08-12T12:00:00+00:00",
        phases=[{"phase": "scope", "status": "ok"}],
    )
    _write_run(
        tmp_path,
        "alpha_v2",
        "20260818T153000Z",
        spec_name="alpha_v2",
        model="anthropic/claude-opus-5",
        ok=True,
        total_cost_usd=2.5,
        git_sha="ccc3333",
        started_at="2026-08-18T14:00:00+00:00",
        ended_at="2026-08-18T15:30:00+00:00",
        phases=[{"phase": "scope", "status": "ok"}, {"phase": "verify", "status": "ok"}],
    )
    return tmp_path


def _by_name(entries: list[SpecStatusEntry]) -> dict[str, SpecStatusEntry]:
    return {e.name: e for e in entries}


def _table_rows(md: str) -> list[str]:
    r"""The data-table rows only.

    The legend below ``## Legend`` is itself a markdown table whose rows also start with
    ``| \``, so every row assertion has to cut the document at the legend heading first.
    """
    body = md.split("## Legend", 1)[0]
    return [ln for ln in body.splitlines() if ln.startswith("| `")]


# ── Timestamp normalization ─────────────────────────────────────


def test_parse_timestamp_handles_every_shape_the_repo_produces():
    # ISO with an explicit offset (workflow_runner._now()), ISO with a Z suffix, and the
    # compact run-ledger filename stem all have to compare against each other.
    iso_offset = parse_timestamp("2026-08-18T15:30:00+00:00")
    iso_zulu = parse_timestamp("2026-08-18T15:30:00Z")
    filename = parse_timestamp("20260818T153000Z")
    assert iso_offset == iso_zulu == filename
    assert iso_offset.tzinfo is not None


def test_parse_timestamp_returns_none_for_garbage():
    assert parse_timestamp(None) is None
    assert parse_timestamp("") is None
    assert parse_timestamp("   ") is None
    assert parse_timestamp("not-a-date") is None


def test_naive_timestamp_is_read_as_utc():
    assert parse_timestamp("2026-08-18T15:30:00") == parse_timestamp("2026-08-18T15:30:00Z")


# ── Status derivation ───────────────────────────────────────────


def _spec(name: str, **kw: object) -> ExperimentSpec:
    return ExperimentSpec(
        name=name,
        question="q",
        version="1",
        workflow=Workflow("agent_task"),
        factors=[Factor("model", ["a"])],
        design="factorial",
        **kw,
    )


def test_derive_status_prefers_the_authored_value():
    # An explicit `draft`/`tombstoned` is a claim only a human can make; it wins over
    # every derivation, even one that would say otherwise.
    assert derive_status(_spec("s", status="draft")) == "draft"
    assert derive_status(_spec("s", status="tombstoned", superseded_by="other")) == "tombstoned"


def test_derive_status_falls_back_to_superseded():
    assert derive_status(_spec("s", superseded_by="other")) == "superseded"


def test_derive_status_defaults_to_runnable():
    # The shape of all 63 committed specs: no lifecycle keys at all. A repeatable spec is
    # always runnable (re-runnable by construction) — the old `active` vocabulary is gone.
    assert derive_status(_spec("s")) == "runnable"


def test_run_history_never_demotes_a_spec_to_draft(repo: Path):
    # "never run" and "draft" are different facts. `gamma` has zero runs and is still
    # runnable; the table reports the absence through n_runs/last_run instead.
    entry = _by_name(collect_entries(root=repo))["gamma"]
    assert entry.status == "runnable"
    assert entry.n_runs == 0


# ── P1-4: per-kind status semantics ─────────────────────────────


def _run(ok: bool | None, *, awaiting: bool = False) -> RunSummary:
    """A minimal run summary with the given success flag (and optional awaiting flag)."""
    return RunSummary(
        path="experiments/results/workflows/wf/run.json", timestamp="", ok=ok, awaiting=awaiting
    )


def _open_run(started_at: str, *, ok: bool | None = None) -> RunSummary:
    """A run that started but never wrote an ``ended_at`` — still in flight, or dead."""
    return RunSummary(
        path="experiments/results/workflows/wf/run.json",
        timestamp=started_at,
        ok=ok,
        started_at=started_at,
        open=True,
    )


#: A fixed "now" for the recency-window tests (review item 8) so the "running vs blocked"
#: boundary is deterministic rather than dependent on the wall clock.
_FIXED_NOW = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


def _workflow(**kw: object) -> ExperimentSpec:
    """A non-repeatable workflow — the P1-4 work-order shape."""
    return _spec("wf", artifact_kind="workflow", repeatable=False, **kw)


def test_nonrepeatable_workflow_never_run_is_runnable():
    assert derive_status(_workflow()) == "runnable"
    assert derive_status(_workflow(), runs=[]) == "runnable"


def test_nonrepeatable_workflow_with_only_failed_runs_is_failed():
    # The P2 fix (review item 8): a definitive failure (ok=False) is `failed`, NOT a
    # permanent `running`. "Attempts but no success" used to derive `running` forever.
    assert derive_status(_workflow(), runs=[_run(False)]) == "failed"
    # A run whose outcome is unrecorded (ok=None) is `blocked` — started, never resolved.
    assert derive_status(_workflow(), runs=[_run(None)]) == "blocked"


def test_historical_failed_or_blocked_run_never_stays_running():
    # The regression pin: nothing that lacks current-execution evidence may derive `running`.
    assert derive_status(_workflow(), runs=[_run(False)]) != "running"
    assert derive_status(_workflow(), runs=[_run(None)]) != "running"


def test_open_run_within_the_window_is_running():
    # An open run (started_at, no ended_at) that is recent IS current execution.
    run = _open_run("2026-08-20T11:00:00+00:00")
    assert derive_status(_workflow(), runs=[run], now=_FIXED_NOW) == "running"


def test_open_run_outside_the_window_is_blocked():
    # An open run that is stale (started days ago, never resolved) is blocked, not running.
    run = _open_run("2026-08-15T11:00:00+00:00")
    assert derive_status(_workflow(), runs=[run], now=_FIXED_NOW) == "blocked"


def test_a_definitive_failure_beats_an_unresolved_run():
    # A mix of ok=False and ok=None yields `failed` (a verdict exists) over `blocked`.
    assert derive_status(_workflow(), runs=[_run(False), _run(None)]) == "failed"


# ── P1: awaiting_approval — a checkpoint-paused run is never "failed" ──────────


def test_nonrepeatable_workflow_whose_latest_run_is_awaiting_is_awaiting_approval():
    # A run ledger with ok=False + awaiting:true (a checkpoint stop, or a resume refused
    # past an unsatisfied checkpoint) is a designed pause for the operator, NOT a failure.
    assert derive_status(_workflow(), runs=[_run(False, awaiting=True)]) == "awaiting_approval"
    # a pause plus an unresolved earlier run is still awaiting — the pause is the verdict
    assert derive_status(_workflow(), runs=[_run(None), _run(False, awaiting=True)]) == (
        "awaiting_approval"
    )


def test_nonrepeatable_workflow_with_a_genuinely_failed_latest_run_is_still_failed():
    # Only a definitive failure (ok=False AND not awaiting) derives `failed` — the P1 fix
    # must not blur the two states together.
    assert derive_status(_workflow(), runs=[_run(False, awaiting=False)]) == "failed"
    assert derive_status(_workflow(), runs=[_run(False)]) == "failed"  # awaiting defaults off


def test_awaiting_approval_is_scoped_to_the_latest_run():
    # The awaiting check keys the LATEST run: a pause predating a later success is shadowed
    # by the one-shot's completion, and a later genuine failure supersedes the pause.
    assert derive_status(_workflow(), runs=[_run(False, awaiting=True), _run(True)]) == "completed"
    assert derive_status(_workflow(), runs=[_run(True), _run(False, awaiting=True)]) == (
        "awaiting_approval"
    )
    assert derive_status(_workflow(), runs=[_run(False, awaiting=True), _run(False)]) == "failed"


def test_awaiting_approval_is_a_distinct_open_status_in_the_table(tmp_path: Path):
    # End-to-end through the ledger: an awaiting:true run ledger derives `awaiting_approval`
    # in the index (not `failed`), and the status appears in STATUS.md's legend.
    specs = tmp_path / "workflows" / "repository"
    specs.mkdir(parents=True)
    (specs / "ship.yaml").write_text(_spec_yaml("ship", repeatable=False, artifact_kind="workflow"))
    _write_run(
        tmp_path,
        "ship",
        "20260820T120000Z",
        spec_name="ship",
        ok=False,
        awaiting=True,
        awaiting_phase="design",
        awaiting_reason="checkpoint",
        started_at="2026-08-20T11:00:00+00:00",
        ended_at="2026-08-20T12:00:00+00:00",
    )
    entry = _by_name(collect_entries(root=tmp_path))["ship"]
    assert entry.status == "awaiting_approval"
    assert entry.latest_ok is False  # the terminal-success bool stays false on the ledger
    assert entry.n_runs == 1
    md = render_status_md(collect_entries(root=tmp_path))
    assert "| `awaiting_approval` |" in md  # the legend documents the new status
    assert "awaiting_approval" in STATUS_ORDER


def test_nonrepeatable_workflow_with_a_successful_run_is_completed():
    assert derive_status(_workflow(), runs=[_run(True)]) == "completed"
    # The split-run guard (engine_gaps_followups g1, F5): a later FAILED re-run of the
    # same revision is evidence the workflow failed — it must NOT stay completed. The old
    # `any(ok is True)` semantic let a failed member hide under an earlier success; a
    # non-repeatable workflow whose latest evidence includes a definitive failure reads
    # failed until a full-coverage run succeeds with no failed member.
    assert derive_status(_workflow(), runs=[_run(True), _run(False)]) == "failed"
    # An awaiting pause predating a later success is shadowed by that success (unchanged).
    assert derive_status(
        _workflow(), runs=[_run(False, awaiting=True), _run(True)]
    ) == "completed"


def test_nonrepeatable_workflow_respects_authored_status_and_supersession():
    # Authored draft/tombstoned are human claims and win over run-derived states.
    assert derive_status(_workflow(status="draft"), runs=[_run(True)]) == "draft"
    assert derive_status(_workflow(status="tombstoned"), runs=[_run(True)]) == "tombstoned"
    # Supersession also wins over a successful run.
    assert derive_status(_workflow(superseded_by="other"), runs=[_run(True)]) == "superseded"


def test_repeatable_spec_never_derives_a_workflow_state_from_runs():
    # A repeatable spec (an experiment, or an idempotent operation) is always `runnable`;
    # run history never folds a `completed`/`running`/`failed`/`blocked` work-order state
    # into its status column.
    assert derive_status(_spec("exp"), runs=[_run(True)]) == "runnable"
    assert derive_status(_spec("exp"), runs=[_run(False)]) == "runnable"
    assert derive_status(_spec("exp", repeatable=True), runs=[_run(True)]) == "runnable"


def test_nonrepeatable_workflow_derives_status_from_ledgers_in_the_index(tmp_path: Path):
    # End-to-end: a non-repeatable workflow under workflows/ derives its index status
    # from the run ledgers, not the YAML.
    specs = tmp_path / "workflows" / "repository"
    specs.mkdir(parents=True)
    (specs / "ship.yaml").write_text(_spec_yaml("ship", repeatable=False, artifact_kind="workflow"))
    _write_run(
        tmp_path,
        "ship",
        "20260820T120000Z",
        spec_name="ship",
        ok=True,
        ended_at="2026-08-20T12:00:00+00:00",
    )
    entry = _by_name(collect_entries(root=tmp_path))["ship"]
    assert entry.status == "completed"
    assert entry.latest_ok is True
    assert entry.n_runs == 1


def test_nonrepeatable_workflow_with_a_failed_ledger_is_failed_not_running(tmp_path: Path):
    # The P2 backfill (review item 8): a run ledger that recorded a definitive failure
    # (ok=False with an ended_at) must derive `failed`, never a stale `running`. This is the
    # exact regression that left old workflows stuck at `running` indefinitely.
    specs = tmp_path / "workflows" / "repository"
    specs.mkdir(parents=True)
    (specs / "ship.yaml").write_text(_spec_yaml("ship", repeatable=False, artifact_kind="workflow"))
    _write_run(
        tmp_path,
        "ship",
        "20260820T120000Z",
        spec_name="ship",
        ok=False,
        started_at="2026-08-20T11:00:00+00:00",
        ended_at="2026-08-20T12:00:00+00:00",
    )
    entry = _by_name(collect_entries(root=tmp_path))["ship"]
    assert entry.status == "failed"
    assert entry.latest_ok is False
    assert entry.n_runs == 1


def test_summary_and_kind_columns_separate_runnable_from_completed(tmp_path: Path):
    # The P1-4 index pass: the summary line answers "what work remains?", and a completed
    # one-shot sorts out of the runnable-now view below it.
    specs = tmp_path / "workflows" / "repository"
    specs.mkdir(parents=True)
    (specs / "todo.yaml").write_text(_spec_yaml("todo", repeatable=False, artifact_kind="workflow"))
    (specs / "done.yaml").write_text(
        _spec_yaml("done", repeatable=False, artifact_kind="workflow", status="completed")
    )
    md = render_status_md(collect_entries(root=tmp_path), generated_at="2026-08-20T00:00:00+00:00")
    assert "**Work remaining:** 1 open · 1 completed/retired" in md
    rows = _table_rows(md)
    assert [r.split("`")[1] for r in rows] == ["todo", "done"]
    # The identity columns are present and populated from the YAML.
    todo_row = next(ln for ln in rows if ln.startswith("| `todo`"))
    assert "| workflow |" in todo_row and "| no |" in todo_row and "| runnable |" in todo_row
    done_row = next(ln for ln in rows if ln.startswith("| `done`"))
    assert "| workflow |" in done_row and "| no |" in done_row and "| completed |" in done_row


# ── Run ledgers ─────────────────────────────────────────────────


def test_load_runs_orders_oldest_first(repo: Path):
    workflows = repo / "experiments" / "results" / "workflows"
    runs = load_runs("alpha_v2", results_dir=workflows, root=repo)
    assert [r.git_sha for r in runs] == ["bbb2222", "ccc3333"]


def test_load_runs_tolerates_a_missing_directory(repo: Path):
    # experiments/results/workflows/ is untracked, so a fresh checkout has nothing here.
    workflows = repo / "experiments" / "results" / "workflows"
    assert load_runs("gamma", results_dir=workflows, root=repo) == []
    assert load_runs("gamma", results_dir=repo / "nope", root=repo) == []


def test_load_runs_skips_a_malformed_ledger_with_a_warning(repo: Path):
    run_dir = repo / "experiments" / "results" / "workflows" / "alpha_v2"
    (run_dir / "20260819T000000Z.json").write_text("{ not json")
    with pytest.warns(UserWarning, match="unreadable run ledger"):
        runs = load_runs("alpha_v2", results_dir=run_dir.parent, root=repo)
    # The two good ledgers survive — one corrupt file must not blank out the spec.
    assert len(runs) == 2


def test_run_timestamp_falls_back_to_the_filename(repo: Path):
    _write_run(repo, "gamma", "20260101T010203Z", spec_name="gamma", ok=True)
    workflows = repo / "experiments" / "results" / "workflows"
    runs = load_runs("gamma", results_dir=workflows, root=repo)
    assert parse_timestamp(runs[0].timestamp) == parse_timestamp("20260101T010203Z")


def test_run_paths_are_repo_relative(repo: Path):
    workflows = repo / "experiments" / "results" / "workflows"
    runs = load_runs("alpha_v2", results_dir=workflows, root=repo)
    assert runs[-1].path == "experiments/results/workflows/alpha_v2/20260818T153000Z.json"


# ── Entry derivation ────────────────────────────────────────────


def test_entry_carries_the_latest_run(repo: Path):
    entry = _by_name(collect_entries(root=repo))["alpha_v2"]
    assert entry.n_runs == 2
    assert entry.latest_ok is True
    assert entry.latest_model == "anthropic/claude-opus-5"
    assert entry.latest_cost_usd == 2.5
    assert entry.latest_git_sha == "ccc3333"  # the *later* run, not the first one
    assert entry.results_pointer.endswith("20260818T153000Z.json")
    assert parse_timestamp(entry.last_run_at) == parse_timestamp("2026-08-18T15:30:00+00:00")


def test_entry_records_a_failed_run_as_such(repo: Path):
    entry = _by_name(collect_entries(root=repo))["alpha_v1"]
    assert entry.latest_ok is False  # measured failure — distinct from "no runs"
    assert entry.n_runs == 1


def test_entry_with_no_runs_leaves_run_fields_unset(repo: Path):
    entry = _by_name(collect_entries(root=repo))["beta_draft"]
    assert entry.n_runs == 0
    assert entry.latest_ok is None
    assert entry.last_run_at is None
    assert entry.results_pointer is None


def test_supersede_lineage_survives_into_the_entries(repo: Path):
    entries = _by_name(collect_entries(root=repo))
    assert entries["alpha_v1"].status == "superseded"
    assert entries["alpha_v1"].superseded_by == "alpha_v2"
    assert entries["alpha_v2"].supersedes == ["alpha_v1"]
    assert entries["alpha_v2"].status == "runnable"
    # The chain is navigable in both directions from the index alone.
    assert entries[entries["alpha_v1"].superseded_by].name == "alpha_v2"


def test_measured_run_beats_the_yaml_seed(tmp_path: Path):
    """The YAML is the seed; a real run ledger is the evidence and wins."""
    specs = tmp_path / "experiments" / "definitions"
    specs.mkdir(parents=True)
    (specs / "seeded.yaml").write_text(
        _spec_yaml(
            "seeded",
            last_run_at="2020-01-01T00:00:00+00:00",
            results_pointer="experiments/results/workflows/seeded/stale.json",
        )
    )
    _write_run(
        tmp_path,
        "seeded",
        "20260820T101112Z",
        spec_name="seeded",
        ok=True,
        ended_at="2026-08-20T10:11:12+00:00",
    )
    entry = _by_name(collect_entries(root=tmp_path))["seeded"]
    assert parse_timestamp(entry.last_run_at) == parse_timestamp("2026-08-20T10:11:12+00:00")
    assert entry.results_pointer.endswith("20260820T101112Z.json")


def test_yaml_seed_survives_when_no_run_ledger_exists(tmp_path: Path):
    """... and with no measured evidence, the authored seed is all there is."""
    specs = tmp_path / "experiments" / "definitions"
    specs.mkdir(parents=True)
    (specs / "seeded.yaml").write_text(
        _spec_yaml(
            "seeded",
            last_run_at="2026-05-05T05:05:05+00:00",
            results_pointer="experiments/results/workflows/seeded/elsewhere.json",
            completed_at="2026-05-06T00:00:00+00:00",
        )
    )
    entry = _by_name(collect_entries(root=tmp_path))["seeded"]
    assert entry.last_run_at == "2026-05-05T05:05:05+00:00"
    assert entry.results_pointer.endswith("elsewhere.json")
    assert entry.completed_at == "2026-05-06T00:00:00+00:00"
    assert entry.n_runs == 0


def test_collect_entries_skips_an_unloadable_spec_with_a_warning(repo: Path):
    # no question/version -> load_spec raises
    (repo / "experiments" / "definitions" / "broken.yaml").write_text("name: broken\n")
    with pytest.warns(UserWarning, match="unloadable spec"):
        entries = collect_entries(root=repo)
    # One broken spec must not hide the other four.
    assert sorted(e.name for e in entries) == ["alpha_v1", "alpha_v2", "beta_draft", "gamma"]


# ── Ordering ────────────────────────────────────────────────────


def test_entries_sort_by_status_then_name(repo: Path):
    entries = collect_entries(root=repo)
    assert [e.name for e in entries] == ["alpha_v2", "gamma", "beta_draft", "alpha_v1"]
    ranks = [STATUS_ORDER.index(e.status) for e in entries]
    assert ranks == sorted(ranks)


def test_sort_entries_puts_an_unknown_status_last():
    rows = [
        SpecStatusEntry(name="weird", version="1", status="mystery", spec_path="a.yaml"),
        SpecStatusEntry(name="zzz", version="1", status="runnable", spec_path="z.yaml"),
    ]
    assert [e.name for e in sort_entries(rows)] == ["zzz", "weird"]


# ── index.json ──────────────────────────────────────────────────


def test_index_schema(repo: Path):
    index = build_index(collect_entries(root=repo), generated_at="2026-08-20T00:00:00+00:00")
    assert index["schema_version"] == INDEX_SCHEMA_VERSION
    assert index["generated_at"] == "2026-08-20T00:00:00+00:00"
    assert index["n_specs"] == 4
    assert len(index["specs"]) == 4

    entry = next(e for e in index["specs"] if e["name"] == "alpha_v2")
    assert set(entry) == {
        "name",
        "version",
        "status",
        "spec_path",
        "artifact_kind",
        "repeatable",
        "supersedes",
        "superseded_by",
        "completed_at",
        "last_run_at",
        "latest_ok",
        "latest_model",
        "latest_cost_usd",
        "latest_git_sha",
        "results_pointer",
        "n_runs",
        # w2 additive keys — present in every entry (never rename/remove a reader's key)
        "workflow_revision_id",
        "authored_status",
    }
    assert entry["spec_path"] == "experiments/definitions/alpha_v2.yaml"


def test_index_is_json_serializable_and_round_trips(repo: Path):
    index = build_index(collect_entries(root=repo))
    restored = [SpecStatusEntry.from_dict(e) for e in json.loads(json.dumps(index))["specs"]]
    assert restored == collect_entries(root=repo)


def test_generated_at_is_present_and_parseable(repo: Path):
    index = build_index(collect_entries(root=repo))
    assert parse_timestamp(index["generated_at"]) is not None


# ── STATUS.md ───────────────────────────────────────────────────


def test_status_md_header_and_columns(repo: Path):
    md = render_status_md(collect_entries(root=repo), generated_at="2026-08-20T00:00:00+00:00")
    assert (
        "| name | kind | repeatable | status | version | supersedes | last_run | ok | model | cost | n_runs |"
        in md
    )
    assert "Generated at: `2026-08-20T00:00:00+00:00`" in md
    assert "4 spec(s)" in md
    assert "**Work remaining:**" in md


def test_status_md_one_row_per_spec_in_sorted_order(repo: Path):
    md = render_status_md(collect_entries(root=repo))
    rows = _table_rows(md)
    assert len(rows) == 4
    assert [r.split("`")[1] for r in rows] == ["alpha_v2", "gamma", "beta_draft", "alpha_v1"]


def test_status_md_renders_measured_values(repo: Path):
    md = render_status_md(collect_entries(root=repo))
    row = next(ln for ln in _table_rows(md) if ln.startswith("| `alpha_v2`"))
    assert "| runnable |" in row
    assert "| 0.2 |" in row
    assert "alpha_v1" in row  # supersedes column
    assert "2026-08-18 15:30" in row  # last_run, shortened
    assert "| ok |" in row
    assert "anthropic/claude-opus-5" in row
    assert "$2.5000" in row
    assert row.rstrip().endswith("| 2 |")  # n_runs


def test_status_md_distinguishes_a_failed_run_from_a_missing_one(repo: Path):
    md = render_status_md(collect_entries(root=repo))
    failed = next(ln for ln in _table_rows(md) if ln.startswith("| `alpha_v1`"))
    never = next(ln for ln in _table_rows(md) if ln.startswith("| `beta_draft`"))
    assert "| fail |" in failed  # measured failure
    assert "| fail |" not in never
    assert f"| {MISSING} |" in never  # no evidence — an em-dash, never a failure


def test_status_md_renders_missing_runs_as_em_dashes(repo: Path):
    md = render_status_md(collect_entries(root=repo))
    row = next(ln for ln in _table_rows(md) if ln.startswith("| `beta_draft`"))
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    name, kind, repeatable, status, version, supersedes, last_run, ok, model, cost, n_runs = cells
    assert (supersedes, last_run, ok, model, cost) == (MISSING,) * 5
    assert (status, n_runs) == ("draft", "0")
    assert kind == "experiment"
    assert repeatable == "yes"


def test_status_md_legend_explains_every_status_and_column(repo: Path):
    md = render_status_md(collect_entries(root=repo))
    assert "## Legend" in md
    for status in STATUS_ORDER:
        assert f"| `{status}` |" in md, f"legend is missing the {status} status"
    for column in ("supersedes", "last_run", "n_runs", "results_pointer"):
        assert column in md, f"legend is missing the {column} column"
    # The em-dash convention is the single most misreadable cell — say it explicitly.
    assert "no evidence" in md


def test_status_md_says_it_is_generated(repo: Path):
    md = render_status_md(collect_entries(root=repo))
    assert "do not edit by hand" in md.lower()
    assert "scripts/spec_status.py" in md


# ── refresh + read-back ─────────────────────────────────────────


def test_refresh_writes_both_artifacts(repo: Path):
    report = refresh_spec_status(root=repo)
    assert report.index_path == repo / "experiments" / "specs" / "index.json"
    assert report.status_path == repo / "experiments" / "specs" / "STATUS.md"
    assert report.n_specs == 4
    assert json.loads(report.index_path.read_text())["n_specs"] == 4
    assert report.status_path.read_text().startswith("# Spec status index")


def test_refresh_is_idempotent_apart_from_the_stamp(repo: Path):
    first = refresh_spec_status(root=repo, generated_at="2026-08-20T00:00:00+00:00")
    body = first.index_path.read_text()
    second = refresh_spec_status(root=repo, generated_at="2026-08-20T00:00:00+00:00")
    assert second.index_path.read_text() == body


def test_refresh_reports_the_requested_spec(repo: Path):
    report = refresh_spec_status("alpha_v2", root=repo)
    assert report.entry_for("alpha_v2").latest_git_sha == "ccc3333"
    assert report.entry_for("nope") is None
    # A spec_name outside the corpus is a warning, not a failure — a spec can be run from
    # a path outside experiments/definitions/.
    with pytest.warns(UserWarning, match="does not contain spec"):
        refresh_spec_status("not_in_corpus", root=repo)


def test_load_index_and_index_entry_read_back(repo: Path):
    refresh_spec_status(root=repo)
    assert load_index(root=repo)["n_specs"] == 4
    entry = index_entry("alpha_v2", root=repo)
    assert entry.results_pointer.endswith("20260818T153000Z.json")
    assert index_entry("nope", root=repo) is None


def test_read_back_never_raises_on_a_missing_or_broken_index(tmp_path: Path):
    # The --resume fallback treats "no index" and "unusable index" identically: fall
    # through to the prior behaviour. Neither may raise.
    assert load_index(root=tmp_path) == {}
    assert index_entry("anything", root=tmp_path) is None
    index_dir = tmp_path / "experiments" / "specs"
    index_dir.mkdir(parents=True)
    (index_dir / "index.json").write_text("{ not json")
    assert load_index(root=tmp_path) == {}
    assert index_entry("anything", root=tmp_path) is None


# ── The real corpus ─────────────────────────────────────────────


def test_the_committed_spec_corpus_indexes_without_exceptions():
    """Every committed spec must appear in the index, derived from the real checkout."""
    entries = collect_entries(root=PROJECT_ROOT)
    committed = sorted((PROJECT_ROOT / "experiments" / "definitions").glob("*.yaml"))
    committed += sorted((PROJECT_ROOT / "workflows").rglob("*.yaml"))
    assert len(committed) >= 63, f"expected the committed corpus, found {len(committed)}"
    assert len(entries) == len(committed), "every committed spec must appear in the index"
    assert all(e.name and e.version for e in entries)
    assert {e.spec_path for e in entries} == {
        p.relative_to(PROJECT_ROOT).as_posix() for p in committed
    }
    # Rendering must be total: no spec, however sparse, may blow up the table.
    md = render_status_md(entries)
    assert len(_table_rows(md)) == len(entries)
    assert all(e.status in STATUS_ORDER for e in entries)


# ── w2: revision identity — completion follows the spec revision ───────────────


def _phase_spec_yaml(name: str, *, phases: list[str], **lifecycle: object) -> str:
    """A workflow spec whose phases carry names (agent/test), mirroring agent_task specs."""
    lines = [
        f"name: {name}",
        "question: gate test?",
        'version: "0.1"',
        "artifact_kind: workflow",
        "repeatable: false",
        "workflow:",
        "  kind: agent_task",
        "  params:",
        "    language: python",
        "    phases:",
    ]
    for ph in phases:
        kind = "test" if ph.endswith("_gate") else "agent"
        lines.append(f"      - name: {ph}")
        lines.append(f"        kind: {kind}")
        lines.append(f"        prompt: do {ph}")
    lines.append("factors:")
    lines.append('  - {name: model, levels: [deepseek/deepseek-v4-pro]}')
    lines.append("design: factorial")
    for key, value in lifecycle.items():
        lines.append(f"{key}: {json.dumps(value)}")
    return "\n".join(lines) + "\n"


def _revision_run(spec: ExperimentSpec, *, ok: bool = True, phases: list[str] | None = None,
                  awaiting: bool = False) -> RunSummary:
    """A run ledger carrying the spec's current revision digest — a post-w2 run."""
    return RunSummary(
        path=f"experiments/results/workflows/{spec.name}/20260902T000000Z.json",
        timestamp="2026-09-02T00:00:00+00:00",
        ok=ok,
        workflow_revision_id=spec.workflow_revision_id,
        executed_phases=frozenset(phases or []),
        awaiting=awaiting,
    )


def test_gate_added_after_completed_shows_never_run_of_this_revision(tmp_path: Path):
    """VERIFY (a): the 'gate added after completed' shape → not completed, never-run.

    A run of the PRE-gate revision (recorded digest of the pre-gate spec) must not mark the
    edited spec (with the appended gate) completed: the current revision has never been run.
    """
    from agentic_dynamics.experiment.experiment_spec import load_spec
    from agentic_dynamics.experiment.spec_status import derive_status

    specs = tmp_path / "workflows" / "repository"
    specs.mkdir(parents=True)
    path = specs / "fleet.yaml"
    path.write_text(_phase_spec_yaml("fleet", phases=["p1", "p2", "p3", "p4", "p5"]))

    # a completed run of revision A (pre-gate) — recorded against A's digest
    spec_a = load_spec(path)
    run_a = _revision_run(spec_a, phases=["p1", "p2", "p3", "p4", "p5"])
    assert derive_status(spec_a, [run_a]) == "completed"

    # append a gate -> revision B. The A-run certifies A only; B is never-run.
    path.write_text(_phase_spec_yaml("fleet", phases=["p1", "p2", "p3", "p4", "p5", "p6_test_gate"]))
    spec_b = load_spec(path)
    assert spec_b.workflow_revision_id != spec_a.workflow_revision_id
    assert derive_status(spec_b, [run_a]) == "runnable"


def test_edited_spec_shows_its_own_revision_run_state(tmp_path: Path):
    """VERIFY (b): a successful run of revision A does NOT mark edited revision B completed."""
    from agentic_dynamics.experiment.experiment_spec import load_spec
    from agentic_dynamics.experiment.spec_status import derive_status

    specs = tmp_path / "workflows" / "repository"
    specs.mkdir(parents=True)
    path = specs / "ship.yaml"
    path.write_text(_phase_spec_yaml("ship", phases=["survey", "design", "implement"]))
    spec_a = load_spec(path)
    run_a = _revision_run(spec_a, phases=["survey", "design", "implement"])
    assert derive_status(spec_a, [run_a]) == "completed"

    path.write_text(_phase_spec_yaml("ship", phases=["survey", "design", "implement_v2"]))
    spec_b = load_spec(path)
    assert derive_status(spec_b, [run_a]) == "runnable"

    # once B itself is run green, B is completed
    run_b = _revision_run(spec_b, phases=["survey", "design", "implement_v2"])
    assert derive_status(spec_b, [run_a, run_b]) == "completed"


def test_legacy_run_without_a_digest_predating_a_gate_does_not_certify(tmp_path: Path):
    """Legacy ledgers (no recorded digest) whose executed phases predate an appended gate
    cannot certify the current revision — the fleet_job_submission corpus shape."""
    from agentic_dynamics.experiment.experiment_spec import load_spec
    from agentic_dynamics.experiment.spec_status import derive_status

    specs = tmp_path / "workflows" / "repository"
    specs.mkdir(parents=True)
    path = specs / "suite.yaml"
    path.write_text(_phase_spec_yaml("suite", phases=["p1", "p2", "p3", "p4", "p5_test_gate"]))

    # legacy run: executed p1..p4 (green) but records NO revision and never ran p5_test_gate
    legacy = RunSummary(
        path="experiments/results/workflows/suite/20260901T000000Z.json",
        timestamp="2026-09-01T00:00:00+00:00",
        ok=True,
        executed_phases=frozenset({"p1", "p2", "p3", "p4"}),
    )
    assert derive_status(load_spec(path), [legacy]) == "runnable"


def test_no_authored_status_and_no_runs_returns_never_run(tmp_path: Path):
    """VERIFY (c): unchanged semantics for the no-revision case."""
    from agentic_dynamics.experiment.spec_status import derive_status

    spec = _workflow()
    assert derive_status(spec) == "runnable"
    assert derive_status(spec, runs=[]) == "runnable"


def test_legacy_authored_status_is_catalogued_with_an_authored_marker(tmp_path: Path):
    """VERIFY (d): legacy authored-status specs get the 'authored' marker path."""
    from agentic_dynamics.experiment.spec_status import collect_entries

    specs = tmp_path / "workflows" / "repository"
    specs.mkdir(parents=True)
    (specs / "done.yaml").write_text(
        _phase_spec_yaml("done", phases=["p1"], status="completed")
    )
    entries = {e.name: e for e in collect_entries(root=tmp_path)}
    entry = entries["done"]
    # no run evidence exists anywhere: the authored claim is the only record, marked authored
    assert entry.status == "completed"
    assert entry.authored_status == "completed"
    assert entry.workflow_revision_id  # non-empty current digest

    # fleet-style: authored completed + run evidence of an OLDER revision -> NOT completed,
    # and the authored claim is preserved as a marker, not silently dropped.
    (specs / "auth.yaml").write_text(
        _phase_spec_yaml("auth", phases=["p1", "p2", "p3", "p4", "p5", "p6_test_gate"], status="completed")
    )
    run_dir = tmp_path / "experiments" / "results" / "workflows" / "auth"
    run_dir.mkdir(parents=True)
    (run_dir / "20260901T000000Z.json").write_text(json.dumps({
        "spec_name": "auth", "ok": True,
        "ended_at": "2026-09-01T00:00:00+00:00",
        "phases": [
            {"phase": "p1", "status": "ok"}, {"phase": "p2", "status": "ok"},
            {"phase": "p3", "status": "ok"}, {"phase": "p4", "status": "ok"},
            {"phase": "p5", "status": "ok"},
        ],
    }))
    from agentic_dynamics.experiment.spec_status import collect_entries as ce
    auth_entry = {e.name: e for e in ce(root=tmp_path)}["auth"]
    assert auth_entry.status == "runnable"  # never run OF THIS REVISION
    assert auth_entry.authored_status == "completed"  # the claim is still visible
    assert auth_entry.n_runs == 1
    assert auth_entry.latest_ok is None  # no run certifies the current revision


def test_index_regeneration_is_deterministic_with_new_fields(tmp_path: Path):
    """VERIFY (d): index regeneration stays deterministic with the additive fields."""
    from agentic_dynamics.experiment.spec_status import (
        refresh_spec_status,
    )

    specs = tmp_path / "workflows" / "repository"
    specs.mkdir(parents=True)
    (specs / "ship.yaml").write_text(_phase_spec_yaml("ship", phases=["p1"]))
    report1 = refresh_spec_status(root=tmp_path, generated_at="2026-09-02T00:00:00+00:00")
    body1 = report1.index_path.read_text()
    report2 = refresh_spec_status(root=tmp_path, generated_at="2026-09-02T00:00:00+00:00")
    assert report2.index_path.read_text() == body1


# ── g1 split-run evidence: the resume family link + the union derivation ──────────
#
# engine_gaps_followups g1 (F5): a --resume continuation is a CHILD of the run it continues,
# recorded as parent_run_id/family_id on the control-db run row AND the run ledger. derive_status
# must derive completion from the UNION of a run family's evidence — never from the latest run
# alone when an earlier member failed or holds un-executed phases.


def _family_run(
    spec: ExperimentSpec,
    *,
    run_id: str,
    family_id: str,
    parent_run_id: str = "",
    ok: bool = True,
    phases: list[str],
    timestamp: str,
    awaiting: bool = False,
) -> RunSummary:
    """A post-g1 run ledger carrying the family link (run_id/parent/family keys)."""
    return RunSummary(
        path=f"experiments/results/workflows/{spec.name}/{timestamp}.json",
        timestamp=timestamp,
        ok=ok,
        workflow_revision_id=spec.workflow_revision_id,
        executed_phases=frozenset(phases),
        awaiting=awaiting,
        run_id=run_id,
        parent_run_id=parent_run_id,
        family_id=family_id,
    )


def _g1_spec_file(root: Path, name: str = "g1_split", phases: list[str] | None = None,
                   **lifecycle: object) -> ExperimentSpec:
    """Write a phase-declaring workflow spec under ``root`` and load it."""
    from agentic_dynamics.experiment.experiment_spec import load_spec

    specs = root / "workflows" / "repository"
    specs.mkdir(parents=True, exist_ok=True)
    path = specs / f"{name}.yaml"
    path.write_text(_phase_spec_yaml(name, phases=phases or ["w1", "w2", "w3", "w4"],
                                     **lifecycle))
    return load_spec(path)


def test_g1_split_run_union_family_completion(tmp_path: Path):
    """VERIFY (a): a linked parent+child derives completed ONLY when the union covers the
    revision AND the latest member succeeded — and derives NOT-completed when a member failed.

    A clean split (parent w1+w2 ok + child w3+w4 ok, same family) reads completed: together
    the family executed the full 4-phase revision, no member failed, and the latest member
    (child) succeeded. The F5 live shape (parent FAILED, child ok) reads NOT-completed even
    though the union still covers and the latest member succeeded — a failed member means the
    failed phase was never re-executed to ok.
    """
    spec = _g1_spec_file(tmp_path, phases=["w1", "w2", "w3", "w4"])
    parent = _family_run(spec, run_id="run-parent", family_id="fam-1", ok=True,
                         phases=["w1", "w2"], timestamp="2026-09-02T10:00:00+00:00")
    child = _family_run(spec, run_id="run-child", family_id="fam-1", parent_run_id="run-parent",
                        ok=True, phases=["w3", "w4"], timestamp="2026-09-02T11:00:00+00:00")
    # Clean split: union covers the full revision, latest member succeeded -> completed.
    assert derive_status(spec, [parent, child]) == "completed"
    # A partial union (w5 missing) is never completed.
    spec5 = _g1_spec_file(tmp_path, name="g1_five", phases=["w1", "w2", "w3", "w4", "w5"])
    p5 = _family_run(spec5, run_id="run-parent", family_id="fam-1", ok=True,
                     phases=["w1", "w2"], timestamp="2026-09-02T10:00:00+00:00")
    c5 = _family_run(spec5, run_id="run-child", family_id="fam-1", parent_run_id="run-parent",
                     ok=True, phases=["w3", "w4"], timestamp="2026-09-02T11:00:00+00:00")
    assert derive_status(spec5, [p5, c5]) == "blocked"
    # The engine_gaps live shape: parent FAILED at w2 -> the family is never completed, even
    # though the union covers and the child (latest) succeeded.
    parent_failed = _family_run(spec, run_id="run-parent", family_id="fam-2", ok=False,
                                phases=["w1", "w2"], timestamp="2026-09-02T10:00:00+00:00")
    child_ok = _family_run(spec, run_id="run-child", family_id="fam-2",
                           parent_run_id="run-parent", ok=True, phases=["w3", "w4"],
                           timestamp="2026-09-02T11:00:00+00:00")
    assert derive_status(spec, [parent_failed, child_ok]) == "failed"
    # Awaiting members are designed stops, never failures: an awaiting parent + ok child
    # (union covers) reads completed.
    parent_await = _family_run(spec, run_id="run-parent", family_id="fam-3", ok=False,
                               awaiting=True, phases=["w1", "w2"],
                               timestamp="2026-09-02T10:00:00+00:00")
    child_after_await = _family_run(spec, run_id="run-child", family_id="fam-3",
                                    parent_run_id="run-parent", ok=True, phases=["w3", "w4"],
                                    timestamp="2026-09-02T11:00:00+00:00")
    assert derive_status(spec, [parent_await, child_after_await]) == "completed"


def test_g1_unlinked_runs_are_separate_families(tmp_path: Path):
    """VERIFY (b): an unlinked second run (a genuinely new attempt) does NOT union with the
    first — two separate families never combine their partial phase coverage."""
    spec = _g1_spec_file(tmp_path, phases=["w1", "w2", "w3", "w4"])
    run_a = _family_run(spec, run_id="run-a", family_id="fam-a", ok=True,
                        phases=["w1", "w2"], timestamp="2026-09-02T10:00:00+00:00")
    # run-b has its OWN family id (a genuinely new attempt) — it must not union with run-a.
    run_b = _family_run(spec, run_id="run-b", family_id="fam-b", ok=True,
                        phases=["w3", "w4"], timestamp="2026-09-02T11:00:00+00:00")
    # Each family alone covers only half the revision -> never completed.
    assert derive_status(spec, [run_a, run_b]) == "blocked"
    # The same two phase halves, family-linked, DO complete (the (a) clean-split shape).
    run_c = _family_run(spec, run_id="run-a", family_id="fam-c", ok=True,
                        phases=["w1", "w2"], timestamp="2026-09-02T10:00:00+00:00")
    run_d = _family_run(spec, run_id="run-b", family_id="fam-c", parent_run_id="run-a",
                        ok=True, phases=["w3", "w4"], timestamp="2026-09-02T11:00:00+00:00")
    assert derive_status(spec, [run_c, run_d]) == "completed"


def test_g1_single_run_derivations_unchanged(tmp_path: Path):
    """VERIFY (c): existing single-run derivations are unchanged — a lone completed run (no
    family fields, full coverage) still reads completed; a lone failed run reads failed."""
    spec = _g1_spec_file(tmp_path, phases=["w1", "w2", "w3", "w4"])
    full = _family_run(spec, run_id="", family_id="", ok=True,
                       phases=["w1", "w2", "w3", "w4"], timestamp="2026-09-02T10:00:00+00:00")
    assert derive_status(spec, [full]) == "completed"
    failed = _family_run(spec, run_id="", family_id="", ok=False,
                         phases=["w1", "w2", "w3", "w4"], timestamp="2026-09-02T10:00:00+00:00")
    assert derive_status(spec, [failed]) == "failed"
    unresolved = _family_run(spec, run_id="", family_id="", ok=None,
                             phases=["w1", "w2", "w3", "w4"], timestamp="2026-09-02T10:00:00+00:00")
    assert derive_status(spec, [unresolved]) == "blocked"


def test_g1_ledger_family_link_round_trips(tmp_path: Path):
    """VERIFY (d): the ledger's family link round-trips — spec_status reads the
    run_id/parent_run_id/family_id keys a resume writes, and derives from the family union."""
    spec = _g1_spec_file(tmp_path, name="g1_rt", phases=["w1", "w2", "w3", "w4"])
    run_dir = tmp_path / "experiments" / "results" / "workflows" / "g1_rt"
    run_dir.mkdir(parents=True, exist_ok=True)

    def _ledger(stem: str, **fields: object) -> Path:
        path = run_dir / f"{stem}.json"
        payload = {
            "spec_name": "g1_rt",
            "goal": "close g1 split-run evidence",
            "ok": True,
            "workflow_revision_id": spec.workflow_revision_id,
            "started_at": "2026-09-02T10:00:00+00:00",
            "ended_at": "2026-09-02T11:00:00+00:00",
            "phases": [],
            **fields,
        }
        path.write_text(json.dumps(payload))
        return path

    _ledger("20260902T100000Z", run_id="run-parent", family_id="fam-rt", ok=True,
            phases=[{"phase": "w1", "status": "ok"}, {"phase": "w2", "status": "ok"}])
    _ledger("20260902T110000Z", run_id="run-child", family_id="fam-rt",
            parent_run_id="run-parent", ok=True,
            phases=[{"phase": "w3", "status": "ok"}, {"phase": "w4", "status": "ok"}])

    runs = load_runs("g1_rt", results_dir=tmp_path / "experiments" / "results" / "workflows",
                     root=tmp_path)
    assert [r.run_id for r in runs] == ["run-parent", "run-child"]
    assert [r.family_id for r in runs] == ["fam-rt", "fam-rt"]
    assert [r.parent_run_id for r in runs] == ["", "run-parent"]
    # The union derivation reads the link straight off the ledgers.
    assert derive_status(spec, runs) == "completed"


# ── g1 revision invalidation: mid-list edits invalidate, partial corpora do not ───────
#
# engine_gaps_followups g1 (F3/F4): _is_definition_changed_after_runs detected only the
# trailing-append shape — a same-count MID-LIST rename (f3) evaded it and certified a legacy
# green run as completed, while a partial-run corpus whose union is a SMALL strict prefix
# (f4, --only-phase p1 runs over p1..p5) false-positived as 'edited'. This family proves the
# two fixes: mid-list structural edits (rename/removal) invalidate by name evidence, and a
# partial-run corpus with no edit reads per its own union instead of 'never run of this
# revision'. Trailing-append detection and full-coverage certification are unchanged.


def _legacy_green_run(spec: ExperimentSpec, phases: list[str],
                      timestamp: str = "2026-09-01T00:00:00+00:00") -> RunSummary:
    """A pre-w2 green run ledger: no digest, no family link — legacy evidence."""
    return RunSummary(
        path=f"experiments/results/workflows/{spec.name}/20260901T000000Z.json",
        timestamp=timestamp,
        ok=True,
        executed_phases=frozenset(phases),
    )


def test_g1_midlist_rename_invalidates_a_legacy_green_run(tmp_path: Path):
    """VERIFY (a): a mid-list RENAME of a phase (same count) invalidates a legacy green run.

    The f3 failure mode: a run of the OLD name set must not certify the renamed definition.
    The run executed a phase (``w2_revision_identity``) the current definition no longer
    declares, so the spec reads never-run-of-this-revision, NOT completed.
    """
    from agentic_dynamics.experiment.spec_status import (
        _is_definition_changed_after_runs,
        derive_status,
    )

    spec_old = _g1_spec_file(tmp_path, name="g1_ren",
                             phases=["w1_pin_spec", "w2_revision_identity", "w3_adversarial"])
    run = _legacy_green_run(spec_old, ["w1_pin_spec", "w2_revision_identity", "w3_adversarial"])
    assert derive_status(spec_old, [run]) == "completed"  # certifies the def it ran

    # rename w2 mid-list, SAME phase count — the f3 shape the old detector could not see.
    spec_new = _g1_spec_file(tmp_path, name="g1_ren",
                             phases=["w1_pin_spec", "w2_revision_invalidation", "w3_adversarial"])
    assert spec_new.workflow_revision_id != spec_old.workflow_revision_id
    assert _is_definition_changed_after_runs(spec_new, [run]) is True
    assert derive_status(spec_new, [run]) == "runnable"  # never run of this revision, not completed


def test_g1_removed_phase_invalidates_legacy_runs(tmp_path: Path):
    """VERIFY (b): a phase REMOVED after the runs invalidates — the runs certify a
    definition that no longer exists."""
    from agentic_dynamics.experiment.spec_status import (
        _is_definition_changed_after_runs,
        derive_status,
    )

    # A full legacy green run of [p1..p4]; p4 is then removed (the definition SHRANK).
    spec_old = _g1_spec_file(tmp_path, name="g1_del", phases=["p1", "p2", "p3", "p4"])
    run = _legacy_green_run(spec_old, ["p1", "p2", "p3", "p4"])
    assert derive_status(spec_old, [run]) == "completed"
    spec_shrunk = _g1_spec_file(tmp_path, name="g1_del", phases=["p1", "p2", "p3"])
    assert _is_definition_changed_after_runs(spec_shrunk, [run]) is True
    assert derive_status(spec_shrunk, [run]) == "runnable"

    # A MID-LIST removal: p2 deleted after the run, p4 stays — same name-evidence invalidates.
    spec_mid = _g1_spec_file(tmp_path, name="g1_del2", phases=["p1", "p3", "p4"])
    run_mid = _legacy_green_run(spec_mid, ["p1", "p2", "p3", "p4"])
    assert _is_definition_changed_after_runs(spec_mid, [run_mid]) is True
    assert derive_status(spec_mid, [run_mid]) == "runnable"


def test_g1_partial_run_corpus_without_an_edit_is_not_edited(tmp_path: Path):
    """VERIFY (c): a partial-run corpus with NO edit does NOT false-positive (the f4 shape).

    A green legacy run that executed only ``p1`` over a ``p1..p5`` definition ran a phase
    that EXISTS in the current definition, in order — it just did not run all of them. That
    is partial, never 'edited': it must derive blocked (per its own union), not the
    'never-run-of-this-revision' runnable an invented definition change would produce.
    """
    from agentic_dynamics.experiment.spec_status import (
        _is_definition_changed_after_runs,
        derive_status,
    )

    spec = _g1_spec_file(tmp_path, name="g1_partial", phases=["p1", "p2", "p3", "p4", "p5"])
    p1_run = _legacy_green_run(spec, ["p1"])
    assert _is_definition_changed_after_runs(spec, [p1_run]) is False
    assert derive_status(spec, [p1_run]) == "blocked"  # partial evidence, never 'edited'

    # A slightly larger prefix corpus (p1+p2 only) is equally partial, not edited.
    p12_run = _legacy_green_run(spec, ["p1", "p2"], timestamp="2026-09-02T00:00:00+00:00")
    assert _is_definition_changed_after_runs(spec, [p12_run]) is False
    assert derive_status(spec, [p12_run]) == "blocked"


def test_g1_trailing_append_still_invalidates(tmp_path: Path):
    """VERIFY (d): a genuine trailing append still invalidates (unchanged).

    The classic appended-gate shape (fleet_job_submission): a legacy green run executed
    every phase the pre-gate definition declared; the current definition appends ONE final
    phase (a test gate) no run ever executed. The runs cannot certify the current revision.
    """
    from agentic_dynamics.experiment.spec_status import (
        _is_definition_changed_after_runs,
        derive_status,
    )

    spec = _g1_spec_file(tmp_path, name="g1_append",
                         phases=["p1", "p2", "p3", "p4", "p5_test_gate"])
    pre_gate = _legacy_green_run(spec, ["p1", "p2", "p3", "p4"])
    assert _is_definition_changed_after_runs(spec, [pre_gate]) is True
    assert derive_status(spec, [pre_gate]) == "runnable"  # never run OF THIS REVISION


def test_g1_full_coverage_legacy_run_still_certifies_completed(tmp_path: Path):
    """VERIFY (e): a full-coverage run of the current definition still certifies completed
    (no regression)."""
    from agentic_dynamics.experiment.spec_status import (
        _is_definition_changed_after_runs,
        derive_status,
    )

    spec = _g1_spec_file(tmp_path, name="g1_full", phases=["w1", "w2", "w3", "w4"])
    full = _legacy_green_run(spec, ["w1", "w2", "w3", "w4"])
    assert _is_definition_changed_after_runs(spec, [full]) is False
    assert derive_status(spec, [full]) == "completed"
