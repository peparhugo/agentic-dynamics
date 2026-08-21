"""Tests for scripts/build_data.py — the phase-2 website registry repoint.

Covers the corpus loader that replaces the retired ``load_summary``/``SUMMARY_PATH``
(read the manifest's ``registry`` array, keep only ``lifecycle_state == "current"`` rows
with ``source_type in {story, finding}``, join measurement payloads) and the two hard
rules the site must obey: tombstoned records are excluded, and a no-op story condition
is relabeled ``clean``. A missing manifest degrades to an empty corpus with a warning.

Every test builds a fixture manifest in ``tmp_path`` and monkeypatches the resolver's
paths (``cc.STORIES_DIR``/``cc.PROJECT_ROOT``) — never the real
``experiments/data_manifest.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_data  # noqa: E402

from agentic_dynamics.reporting import canonical_corpus as cc  # noqa: E402


def _row(**overrides) -> dict:
    """A minimal registry index row, defaulting to a current ``story``."""
    base = {
        "knowledge_id": "kid_0001",
        "entity_id": "eid_0001",
        "source_type": "story",
        "logical_locator": "story_abc",
        "source_uri": "story:story_abc",
        "lifecycle_state": "current",
        "observed_at": "2026-08-15T00:00:00+00:00",
        "indexed_at": "2026-08-15T00:00:01+00:00",
        "supersedes": None,
        "causes": None,
        "reason": "",
    }
    base.update(overrides)
    return base


def _write_manifest(path: Path, rows: list) -> None:
    """Write a manifest JSON with just the fields ``load_registry`` reads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": "1.0", "registry": rows}))


def _story_payload(story_id: str, *, condition: str, instrumented: bool) -> dict:
    """A ``StoryResult.to_dict()``-shaped payload for one story cell.

    ``instrumented`` controls whether ``test_executed_success`` is a real bool (the
    independent test runner measured it) — the signal that distinguishes a genuine
    perturbation from a pre-fix no-op.
    """
    return {
        "story_id": story_id,
        "story_name": "notification_service",
        "model": "anthropic/claude-haiku-4-5",
        "perturbation_condition": condition,
        "test_executed_success": True if instrumented else None,
        "perturbation_strength": 0.5 if instrumented else None,
        "language": "python",
        "summary": {"total_cost": 1.0, "session_count": 5},
        "sessions": [],
    }


# ── corpus loading ────────────────────────────────────────────────


def test_missing_manifest_degrades_with_a_warning(tmp_path, capsys):
    """A missing manifest is not a hard failure — empty corpus + a stderr warning."""
    corpus = build_data.load_canonical_corpus(tmp_path / "does_not_exist.json")
    err = capsys.readouterr().err

    assert "WARNING" in err
    assert corpus.entries == []
    assert corpus.stories == []
    assert corpus.story_count == 0
    assert corpus.finding_count == 0
    assert corpus.tombstoned_count == 0


def test_tombstoned_story_records_are_excluded(tmp_path, monkeypatch):
    """Only ``lifecycle_state == "current"`` stories become measurements.

    A tombstoned story row (the contaminated ``early_degrade`` cells) must never
    contribute a payload, and its count is reported separately.
    """
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    # The current story's payload file (filename ends in _cur.json).
    (stories_dir / "note_service_cur.json").write_text(
        json.dumps(_story_payload("cur", condition="clean", instrumented=False))
    )

    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [
        _row(knowledge_id="kid_cur", entity_id="eid_cur",
             logical_locator="cur", source_uri="story:cur"),
        _row(knowledge_id="kid_bad", entity_id="eid_bad",
             logical_locator="bad", source_uri="story:bad",
             lifecycle_state="tombstoned", reason="contaminated: ran as clean (P0-7)"),
    ])
    monkeypatch.setattr(cc, "STORIES_DIR", stories_dir)

    corpus = build_data.load_canonical_corpus(manifest_path)

    assert corpus.story_count == 1
    assert corpus.tombstoned_count == 1
    assert len(corpus.stories) == 1
    assert corpus.stories[0]["_registry"]["source_uri"] == "story:cur"


def test_tombstoned_finding_records_are_excluded(tmp_path, monkeypatch):
    """The same current-only filter applies to ``finding`` rows."""
    results_dir = tmp_path / "experiments" / "results"
    results_dir.mkdir(parents=True)
    payload_path = results_dir / "task_manager_deepseek-v4-pro.json"
    payload_path.write_text(json.dumps({
        "experiment": "task_manager",
        "runs": [{
            "type": "baseline", "model": "deepseek/deepseek-v4-pro",
            "workdir": "/tmp/exp_good", "cost_usd": 0.01, "correctness": 1.0,
            "tests_total": 9, "tests_passed": 9, "test_executed_success": True,
        }],
    }))

    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [
        _row(knowledge_id="kid_f_good", entity_id="eid_f_good", source_type="finding",
             logical_locator="exp_good",
             source_uri="file://experiments/results/task_manager_deepseek-v4-pro.json"),
        _row(knowledge_id="kid_f_bad", entity_id="eid_f_bad", source_type="finding",
             logical_locator="exp_bad",
             source_uri="file://experiments/results/task_manager_deepseek-v4-pro.json",
             lifecycle_state="tombstoned", reason="contaminated"),
    ])
    monkeypatch.setattr(cc, "PROJECT_ROOT", tmp_path)

    corpus = build_data.load_canonical_corpus(manifest_path)

    assert corpus.finding_count == 1
    assert corpus.tombstoned_count == 1
    assert len(corpus.entries) == 1
    assert corpus.entries[0]["worktree_name"] == "exp_good"


# ── no-op condition relabel ───────────────────────────────────────


def test_noop_story_condition_is_relabeled_clean(tmp_path, monkeypatch):
    """A non-instrumented ``early_degrade`` story is a no-op → relabeled ``clean``."""
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    (stories_dir / "note_service_noop.json").write_text(
        json.dumps(_story_payload("noop", condition="early_degrade", instrumented=False))
    )

    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [
        _row(logical_locator="noop", source_uri="story:noop"),
    ])
    monkeypatch.setattr(cc, "STORIES_DIR", stories_dir)

    corpus = build_data.load_canonical_corpus(manifest_path)

    assert corpus.stories[0]["_canonical_condition"] == "clean"


def test_instrumented_story_keeps_its_condition(tmp_path, monkeypatch):
    """An instrumented ``early_degrade`` story genuinely perturbed → label preserved."""
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    (stories_dir / "note_service_real.json").write_text(
        json.dumps(_story_payload("real", condition="early_degrade", instrumented=True))
    )

    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [
        _row(logical_locator="real", source_uri="story:real"),
    ])
    monkeypatch.setattr(cc, "STORIES_DIR", stories_dir)

    corpus = build_data.load_canonical_corpus(manifest_path)

    assert corpus.stories[0]["_canonical_condition"] == "early_degrade"


def test_genuinely_clean_story_is_untouched(tmp_path, monkeypatch):
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    (stories_dir / "note_service_clean.json").write_text(
        json.dumps(_story_payload("clean", condition="clean", instrumented=True))
    )

    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [
        _row(logical_locator="clean", source_uri="story:clean"),
    ])
    monkeypatch.setattr(cc, "STORIES_DIR", stories_dir)

    corpus = build_data.load_canonical_corpus(manifest_path)
    assert corpus.stories[0]["_canonical_condition"] == "clean"


# ── finding payload → entry mapping ───────────────────────────────


def test_finding_row_joins_to_its_run(tmp_path, monkeypatch):
    """A current finding row joins via source_uri + logical_locator (workdir basename)."""
    results_dir = tmp_path / "experiments" / "results"
    results_dir.mkdir(parents=True)
    payload_path = results_dir / "task_manager_deepseek-v4-pro.json"
    payload_path.write_text(json.dumps({
        "experiment": "task_manager",
        "runs": [
            {
                "type": "baseline", "model": "deepseek/deepseek-v4-pro",
                "workdir": "/tmp/exp_other", "cost_usd": 0.0, "correctness": 1.0,
                "tests_total": 9, "tests_passed": 9, "test_executed_success": True,
            },
            {
                "type": "perturbed", "model": "deepseek/deepseek-v4-pro",
                "operator": "inject_alien_vocab", "perturbation_class": "process_perturbation",
                "workdir": "/tmp/exp_jgikdggu", "cost_usd": 0.019886315,
                "correctness": 0.982, "tests_total": 56, "tests_passed": 55,
                "test_executed_success": False, "lines_of_code": 965,
                "escape_score": 0.76, "thinking_ratio": 0.093,
            },
        ],
    }))

    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [
        _row(knowledge_id="kid_f", entity_id="eid_f", source_type="finding",
             logical_locator="exp_jgikdggu",
             source_uri="file://experiments/results/task_manager_deepseek-v4-pro.json"),
    ])
    monkeypatch.setattr(cc, "PROJECT_ROOT", tmp_path)

    corpus = build_data.load_canonical_corpus(manifest_path)

    assert len(corpus.entries) == 1
    entry = corpus.entries[0]
    # The workdir basename is the join key inside the runs[] array.
    assert entry["worktree_name"] == "exp_jgikdggu"
    assert entry["experiment"] == "task_manager"
    assert entry["model"] == "deepseek/deepseek-v4-pro"
    assert entry["cost"] == 0.019886315          # cost_usd → cost
    assert entry["test_results"] == {"total": 56, "passed": 55}
    assert entry["perturbation_class"] == "process_perturbation"
    assert entry["code_lines"] == 965            # lines_of_code → code_lines


# ── pass-rate honesty + historical sections ───────────────────────


def test_pass_rate_is_none_when_no_measured_tests():
    """Never fabricate a pass rate — unmeasured tests render as None (em-dash)."""
    entry = build_data._finding_entry_from_run("task_manager", {
        "type": "baseline", "model": "deepseek/deepseek-v4-pro",
        "workdir": "/tmp/exp_x", "cost_usd": 0.01, "correctness": 1.0,
        "tests_total": 0, "tests_passed": 0, "test_executed_success": False,
    }, "exp_x")
    models = build_data.compute_model_data([entry])
    assert models[0]["pass_rate"] is None


def test_pass_rate_derived_from_measured_tests():
    """A measured test result produces a real (non-fabricated) pass-rate string."""
    entry = build_data._finding_entry_from_run("task_manager", {
        "type": "baseline", "model": "deepseek/deepseek-v4-pro",
        "workdir": "/tmp/exp_y", "cost_usd": 0.01, "correctness": 1.0,
        "tests_total": 50, "tests_passed": 45, "test_executed_success": True,
    }, "exp_y")
    models = build_data.compute_model_data([entry])
    assert models[0]["pass_rate"] == "90% (45/50) [tests]"


def test_sonar_section_is_marked_historical():
    """Sonar per-cell aggregates have no canonical replacement → [P] historical marker."""
    sonar = build_data._compute_sonar([])
    assert sonar["_historical"] is True
    assert "[P]" in sonar["_note"]
    assert sonar["models"] == {}


def test_missing_payload_resolves_to_nothing(tmp_path, monkeypatch):
    """A current story row whose payload file is absent contributes nothing."""
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()  # empty — no payload file for the row

    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [
        _row(logical_locator="orphan", source_uri="story:orphan"),
    ])
    monkeypatch.setattr(cc, "STORIES_DIR", stories_dir)

    corpus = build_data.load_canonical_corpus(manifest_path)

    # The row is still counted as a current story, but yields no measurement payload.
    assert corpus.story_count == 1
    assert corpus.stories == []


# ---------------------------------------------------------------------------
# The publication gate (semantic-integrity release s1 + s2)
# ---------------------------------------------------------------------------


def _lab_gate_fixture(tmp_path, monkeypatch, *, contract_ok: bool):
    """Point build_data at a synthetic manifest + one publication-eligible lab artifact.

    Returns the identity the artifact was built against. When ``contract_ok`` is False the
    artifact embeds a DIFFERENT registry's hash — the stale case build_data must reject.
    """
    from agentic_dynamics.reporting import canonical_corpus as cc
    from agentic_dynamics.reporting.lab_contract import CONTRACT_KEY, build_contract

    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [_row(logical_locator="s1", source_uri="story:s1")])

    # The corpus the artifact claims to have been built from.
    claimed = manifest_path
    if not contract_ok:
        claimed = tmp_path / "older_manifest.json"
        _write_manifest(claimed, [_row(logical_locator="OLD", source_uri="story:OLD")])

    tables = cc.load_canonical_tables("story", manifest_path=claimed)
    artifact = tmp_path / "lab_story_arc.json"
    artifact.write_text(json.dumps({
        "experiment_id": "lab_story_arc",
        CONTRACT_KEY: build_contract("lab_story_arc.py", tables),
    }))

    # build_data resolves lab outputs relative to ROOT; point ROOT at tmp_path and make the
    # manifest entry's `output` land on our artifact.
    monkeypatch.setattr(build_data, "ROOT", tmp_path)
    monkeypatch.setattr(build_data, "MANIFEST_PATH", manifest_path)

    from agentic_dynamics.reporting import lab_manifest as lm

    real = lm.load_lab_manifest()
    entry = real.get("lab_story_arc.py")
    assert entry is not None
    only = lm.LabManifest(
        schema_version=real.schema_version,
        entries={"lab_story_arc.py": lm.LabEntry(**{
            **{f.name: getattr(entry, f.name) for f in entry.__dataclass_fields__.values()},
            "output": "lab_story_arc.json",
        })},
    )
    monkeypatch.setattr(build_data, "load_lab_manifest", lambda: only)
    return only


def test_lab_gate_publishes_a_contract_valid_artifact(tmp_path, monkeypatch, capsys):
    """A fresh, contract-bearing lab artifact reaches data.js."""
    _lab_gate_fixture(tmp_path, monkeypatch, contract_ok=True)
    labs = build_data._load_labs()
    assert "story_arc" in labs
    assert "rejected" not in capsys.readouterr().out


def test_lab_gate_rejects_a_stale_manifest_lab_json(tmp_path, monkeypatch, capsys):
    """A lab JSON whose embedded manifest hash is stale is refused — and logged by name."""
    _lab_gate_fixture(tmp_path, monkeypatch, contract_ok=False)
    labs = build_data._load_labs()

    assert labs == {}, "a stale lab artifact must not be published"
    out = capsys.readouterr().out
    assert "[lab-gate] rejected" in out
    assert "lab_story_arc.py" in out, "the rejection must name the lab"
    assert "stale registry_identity_sha256" in out


# ---------------------------------------------------------------------------
# Resolution completeness + fail-closed (canonical-publication closure, phase c2)
# ---------------------------------------------------------------------------


def test_resolution_report_counts_missing_payload(tmp_path, monkeypatch):
    """A current story row with no payload file is a ``missing`` issue, not a silent drop."""
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [_row(logical_locator="orphan", source_uri="story:orphan")])
    monkeypatch.setattr(cc, "STORIES_DIR", stories_dir)

    tables = cc.load_canonical_tables("story", manifest_path=manifest_path)
    r = tables.resolution

    assert r.expected_current == 1
    assert r.resolved == 0
    assert r.missing == 1
    assert r.unresolved == 1
    assert not r.complete
    assert tables.stories == []


def test_resolution_report_flags_unreadable_payload(tmp_path, monkeypatch):
    """A payload file that is not valid JSON is ``unreadable``, not ``missing``."""
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    (stories_dir / "note_service_bad.json").write_text("{ not valid json")
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [_row(logical_locator="bad", source_uri="story:bad")])
    monkeypatch.setattr(cc, "STORIES_DIR", stories_dir)

    tables = cc.load_canonical_tables("story", manifest_path=manifest_path)
    assert tables.resolution.unreadable == 1
    assert tables.resolution.missing == 0


def test_resolution_report_flags_ambiguous_payload(tmp_path, monkeypatch):
    """Two payload files matching one locator is ``ambiguous``."""
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    payload = json.dumps(_story_payload("dup", condition="clean", instrumented=True))
    (stories_dir / "a_dup.json").write_text(payload)
    (stories_dir / "b_dup.json").write_text(payload)
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [_row(logical_locator="dup", source_uri="story:dup")])
    monkeypatch.setattr(cc, "STORIES_DIR", stories_dir)

    tables = cc.load_canonical_tables("story", manifest_path=manifest_path)
    assert tables.resolution.ambiguous == 1


def test_resolution_report_flags_duplicate_rows(tmp_path, monkeypatch):
    """Two current rows sharing a locator is a ``duplicate`` defect."""
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    (stories_dir / "note_service_dup.json").write_text(
        json.dumps(_story_payload("dup", condition="clean", instrumented=True))
    )
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [
        _row(knowledge_id="k1", entity_id="e1", logical_locator="dup", source_uri="story:dup"),
        _row(knowledge_id="k2", entity_id="e2", logical_locator="dup", source_uri="story:dup"),
    ])
    monkeypatch.setattr(cc, "STORIES_DIR", stories_dir)

    tables = cc.load_canonical_tables("story", manifest_path=manifest_path)
    assert tables.resolution.duplicate == 1
    assert tables.resolution.expected_current == 2


def test_fail_closed_on_unwaivered_missing_row(tmp_path, monkeypatch):
    """A missing payload without a waiver aborts publication."""
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [_row(logical_locator="orphan", source_uri="story:orphan")])
    monkeypatch.setattr(cc, "STORIES_DIR", stories_dir)

    tables = cc.load_canonical_tables("story", manifest_path=manifest_path)
    with pytest.raises(RuntimeError, match="not covered by a waiver"):
        build_data._assert_resolution_complete(tables, waiver_path=tmp_path / "absent.json")


def test_fail_closed_passes_with_waiver_and_waiver_visible(tmp_path, monkeypatch):
    """A missing payload with a reason-bearing waiver builds, and the waiver is returned."""
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [_row(logical_locator="orphan", source_uri="story:orphan")])
    monkeypatch.setattr(cc, "STORIES_DIR", stories_dir)

    tables = cc.load_canonical_tables("story", manifest_path=manifest_path)
    waiver_path = tmp_path / "waivers.json"
    waiver_path.write_text(json.dumps({
        "schema_version": "waiver/v1",
        "waivers": [
            {"table": "story", "logical_locator": "orphan", "entity_id": None,
             "reason": "known payload-less stub"},
        ],
    }))

    waived = build_data._assert_resolution_complete(tables, waiver_path=waiver_path)
    assert len(waived) == 1
    assert waived[0]["logical_locator"] == "orphan"
    assert waived[0]["reason"] == "known payload-less stub"


def test_real_corpus_resolution_is_waivered():
    """The committed corpus resolves once the 10 payload-less rows are waived.

    An integration guard: if a new payload-less current row appears without a matching
    waiver, this raises — publication fails closed against drift, not just in fixtures.
    """
    if not cc.current_manifest_identity().registry_identity_sha256:  # pragma: no cover
        pytest.skip("no data_manifest.json registry in this checkout")
    tables = cc.load_canonical_tables("story", "finding", "review")
    waived = build_data._assert_resolution_complete(tables)
    assert tables.resolution.missing == 10
    assert len(waived) == 10
