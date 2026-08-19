"""Tests for the derived spec lifecycle index (``instrument.spec_status``).

Everything here runs against a synthetic repo built in ``tmp_path`` — a ``experiments/specs/``
of fixture YAMLs plus a ``experiments/results/workflows/<name>/*.json`` of fixture run
ledgers — so the assertions are exact rather than "whatever the real corpus happens to
contain today". The one exception is the final test, which scans the real checkout to prove
the whole committed corpus indexes without an exception.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from instrument.experiment_spec import ExperimentSpec, Factor, Workflow
from instrument.spec_status import (
    INDEX_SCHEMA_VERSION,
    MISSING,
    STATUS_ORDER,
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
    specs = tmp_path / "experiments" / "specs"
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
        tmp_path, "alpha_v1", "20260810T090000Z",
        spec_name="alpha_v1", model="deepseek/deepseek-v4-pro", ok=False,
        total_cost_usd=0.5, git_sha="aaa1111",
        started_at="2026-08-10T08:00:00+00:00", ended_at="2026-08-10T09:00:00+00:00",
        phases=[{"phase": "scope", "status": "failed"}],
    )
    _write_run(
        tmp_path, "alpha_v2", "20260812T120000Z",
        spec_name="alpha_v2", model="anthropic/claude-opus-5", ok=True,
        total_cost_usd=1.25, git_sha="bbb2222",
        started_at="2026-08-12T11:00:00+00:00", ended_at="2026-08-12T12:00:00+00:00",
        phases=[{"phase": "scope", "status": "ok"}],
    )
    _write_run(
        tmp_path, "alpha_v2", "20260818T153000Z",
        spec_name="alpha_v2", model="anthropic/claude-opus-5", ok=True,
        total_cost_usd=2.5, git_sha="ccc3333",
        started_at="2026-08-18T14:00:00+00:00", ended_at="2026-08-18T15:30:00+00:00",
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
        name=name, question="q", version="1",
        workflow=Workflow("agent_task"), factors=[Factor("model", ["a"])],
        design="factorial", **kw,
    )


def test_derive_status_prefers_the_authored_value():
    # An explicit `draft`/`tombstoned` is a claim only a human can make; it wins over
    # every derivation, even one that would say otherwise.
    assert derive_status(_spec("s", status="draft")) == "draft"
    assert derive_status(_spec("s", status="tombstoned", superseded_by="other")) == "tombstoned"


def test_derive_status_falls_back_to_superseded():
    assert derive_status(_spec("s", superseded_by="other")) == "superseded"


def test_derive_status_defaults_to_active():
    # The shape of all 63 committed specs: no lifecycle keys at all.
    assert derive_status(_spec("s")) == "active"


def test_run_history_never_demotes_a_spec_to_draft(repo: Path):
    # "never run" and "draft" are different facts. `gamma` has zero runs and is still
    # active; the table reports the absence through n_runs/last_run instead.
    entry = _by_name(collect_entries(root=repo))["gamma"]
    assert entry.status == "active"
    assert entry.n_runs == 0


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
    assert entries["alpha_v2"].status == "active"
    # The chain is navigable in both directions from the index alone.
    assert entries[entries["alpha_v1"].superseded_by].name == "alpha_v2"


def test_measured_run_beats_the_yaml_seed(tmp_path: Path):
    """The YAML is the seed; a real run ledger is the evidence and wins."""
    specs = tmp_path / "experiments" / "specs"
    specs.mkdir(parents=True)
    (specs / "seeded.yaml").write_text(
        _spec_yaml(
            "seeded",
            last_run_at="2020-01-01T00:00:00+00:00",
            results_pointer="experiments/results/workflows/seeded/stale.json",
        )
    )
    _write_run(
        tmp_path, "seeded", "20260820T101112Z",
        spec_name="seeded", ok=True, ended_at="2026-08-20T10:11:12+00:00",
    )
    entry = _by_name(collect_entries(root=tmp_path))["seeded"]
    assert parse_timestamp(entry.last_run_at) == parse_timestamp("2026-08-20T10:11:12+00:00")
    assert entry.results_pointer.endswith("20260820T101112Z.json")


def test_yaml_seed_survives_when_no_run_ledger_exists(tmp_path: Path):
    """... and with no measured evidence, the authored seed is all there is."""
    specs = tmp_path / "experiments" / "specs"
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
    (repo / "experiments" / "specs" / "broken.yaml").write_text("name: broken\n")
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
        SpecStatusEntry(name="zzz", version="1", status="active", spec_path="z.yaml"),
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
        "name", "version", "status", "spec_path", "supersedes", "superseded_by",
        "completed_at", "last_run_at", "latest_ok", "latest_model", "latest_cost_usd",
        "latest_git_sha", "results_pointer", "n_runs",
    }
    assert entry["spec_path"] == "experiments/specs/alpha_v2.yaml"


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
    assert "| name | status | version | supersedes | last_run | ok | model | cost | n_runs |" in md
    assert "Generated at: `2026-08-20T00:00:00+00:00`" in md
    assert "4 spec(s)" in md


def test_status_md_one_row_per_spec_in_sorted_order(repo: Path):
    md = render_status_md(collect_entries(root=repo))
    rows = _table_rows(md)
    assert len(rows) == 4
    assert [r.split("`")[1] for r in rows] == ["alpha_v2", "gamma", "beta_draft", "alpha_v1"]


def test_status_md_renders_measured_values(repo: Path):
    md = render_status_md(collect_entries(root=repo))
    row = next(ln for ln in _table_rows(md) if ln.startswith("| `alpha_v2`"))
    assert "| active |" in row
    assert "| 0.2 |" in row
    assert "alpha_v1" in row                  # supersedes column
    assert "2026-08-18 15:30" in row          # last_run, shortened
    assert "| ok |" in row
    assert "anthropic/claude-opus-5" in row
    assert "$2.5000" in row
    assert row.rstrip().endswith("| 2 |")     # n_runs


def test_status_md_distinguishes_a_failed_run_from_a_missing_one(repo: Path):
    md = render_status_md(collect_entries(root=repo))
    failed = next(ln for ln in _table_rows(md) if ln.startswith("| `alpha_v1`"))
    never = next(ln for ln in _table_rows(md) if ln.startswith("| `beta_draft`"))
    assert "| fail |" in failed          # measured failure
    assert "| fail |" not in never
    assert f"| {MISSING} |" in never     # no evidence — an em-dash, never a failure


def test_status_md_renders_missing_runs_as_em_dashes(repo: Path):
    md = render_status_md(collect_entries(root=repo))
    row = next(ln for ln in _table_rows(md) if ln.startswith("| `beta_draft`"))
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    name, status, version, supersedes, last_run, ok, model, cost, n_runs = cells
    assert (supersedes, last_run, ok, model, cost) == (MISSING,) * 5
    assert (status, n_runs) == ("draft", "0")


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
    # a path outside experiments/specs/.
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
    specs = tmp_path / "experiments" / "specs"
    specs.mkdir(parents=True)
    (specs / "index.json").write_text("{ not json")
    assert load_index(root=tmp_path) == {}
    assert index_entry("anything", root=tmp_path) is None


# ── The real corpus ─────────────────────────────────────────────


def test_the_committed_spec_corpus_indexes_without_exceptions():
    """Every committed spec must appear in the index, derived from the real checkout."""
    entries = collect_entries(root=PROJECT_ROOT)
    committed = sorted((PROJECT_ROOT / "experiments" / "specs").glob("*.yaml"))
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
