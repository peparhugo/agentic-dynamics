"""Hermetic tests for the additive story/summary corpus families (CAP fact backfill, p3).

``tests/test_kb_produce_facts_integration.py`` covers the workflow-run producer end-to-end; this
file covers the ADDITIVE extension in ``scripts/kb_produce_facts.py`` — the ``story_session`` /
``story_result`` / ``summary_attempt`` evidence families projected onto the UNCHANGED
``attempt_facts/v1`` / ``job_facts/v1`` reducers. It follows the same hermetic pattern: the module
is re-rooted at ``tmp_path`` (so neither the real ``experiments/results/stories/``,
``_results_summary.json``, nor ``registry_index.jsonl`` is touched), fixture story cells + summary
entries are written to the hermetic tree, and derivation runs through the real producer functions
(``load_story_cells`` / ``load_summary_entries`` -> ``_story_*_evidence`` -> ``derive_*_facts``).

GUARD (no Redis/network): only the pure derivation path is exercised — never ``main()`` /
``emit_records()``. Registry persistence is simulated with the same mirrored ``kb-registry-v1``
registration line the sibling integration test uses.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from agentic_dynamics.control import fact_ingestion as fi
from agentic_dynamics.control.facts import EvidenceItem
from agentic_dynamics.control.reducers._common import run_artifact_id

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO = "agentic-dynamics"
REVISION = "0123456789abcdef0123456789abcdef01234567"
NOW = "2026-08-23T00:00:00+00:00"


def _load_kb_produce_facts():
    """Import ``scripts/kb_produce_facts.py`` as a module (the sibling integration test's pattern)."""
    spec = importlib.util.spec_from_file_location(
        "kb_produce_facts_extension_under_test", PROJECT_ROOT / "scripts" / "kb_produce_facts.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def kpf(tmp_path, monkeypatch):
    """A fresh ``kb_produce_facts`` module, hermetically re-rooted at ``tmp_path``.

    ``REPO_ROOT`` drives ``load_story_cells``/``load_summary_entries``/``load_run_jsons``;
    ``REGISTRY_INDEX_PATH`` drives every ``fact_ingestion.derive_fact_records`` call. Neither the
    real repo's corpus nor its ``registry_index.jsonl`` is ever touched.
    """
    module = _load_kb_produce_facts()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    return module


def _write_story_cell(
    tmp_path: Path,
    filename: str,
    *,
    story: str = "task_manager_api",
    condition: str = "clean",
    model: str = "deepseek/deepseek-v4-pro",
    completed_at: str = "2026-08-20T00:00:00+00:00",
    error: str = "",
    total_cost: float = 1.5,
    all_successful: bool = True,
    sessions: list | None = None,
) -> dict:
    """Write one story result cell JSON to the hermetic tree; return the dict written."""
    sessions = sessions or [
        {
            "session_number": 1,
            "exit_code": 0,
            "commit_hash": "aaa111",
            "cost_usd": 0.5,
            "confidence": 0.9,
        },
        {
            "session_number": 2,
            "exit_code": 0,
            "commit_hash": "bbb222",
            "cost_usd": 1.0,
        },
    ]
    cell = {
        "story_name": story,
        "story_id": filename,
        "model": model,
        "perturbation_condition": condition,
        "started_at": "2026-08-20T00:00:00+00:00",
        "completed_at": completed_at,
        "error": error,
        "summary": {
            "total_cost": total_cost,
            "total_tokens": 1234,
            "all_successful": all_successful,
            "cache_hit_rate": 0.8,
        },
        "sessions": sessions,
    }
    out_dir = tmp_path / "experiments" / "results" / "stories"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{filename}.json").write_text(json.dumps(cell))
    return cell


def _write_summary(tmp_path: Path, entries: list[dict]) -> dict:
    """Write the ``_results_summary.json`` corpus to the hermetic tree; return the payload."""
    payload = {"_meta": {"total_entries": len(entries)}, "entries": entries}
    out_dir = tmp_path / "experiments" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_results_summary.json").write_text(json.dumps(payload))
    return payload


def _registration_line(record) -> dict:
    """The line ``kb_worker.py``'s ``kb-registry-v1`` handler would append for one record (the
    sibling integration test's helper, mirrored field-for-field)."""
    return {
        "knowledge_id": record.knowledge_id,
        "entity_id": record.entity_id,
        "source_type": record.source_type,
        "logical_locator": record.logical_locator,
        "source_uri": record.source_uri,
        "lifecycle_state": "current",
        "observed_at": record.observed_at,
        "indexed_at": record.indexed_at,
        "supersedes": record.supersedes,
        "causes": record.causes,
        "reason": fi.fact_reason(record),
    }


def _persist(registry_path: Path, *records) -> None:
    """Append registration lines for ``records`` to the hermetic registry."""
    lines = "".join(json.dumps(_registration_line(r)) + "\n" for r in records)
    with registry_path.open("a") as f:
        f.write(lines)


def _pred(record) -> str:
    """The predicate of a fact record (parsed from its canonical payload)."""
    return json.loads(record.text)["predicate"]


# ── 1. Story derivation: succeeds, ids stable, absent fields stay absent ──


def test_story_derivation_succeeds_and_ids_are_stable(kpf, tmp_path):
    _write_story_cell(tmp_path, "cell_one", sessions=[
        {"session_number": 1, "exit_code": 0, "commit_hash": "aaa111",
         "cost_usd": 0.5, "confidence": 0.9},
        {"session_number": 2, "exit_code": 0, "commit_hash": "bbb222",
         "cost_usd": 1.0, "confidence": None},
    ])

    round_1 = kpf.derive_story_facts(REPO, REVISION, NOW)
    assert round_1, "story derivation must succeed and produce facts"
    assert all(r.supersedes is None for r in round_1)  # empty registry -> all first versions

    preds = {_pred(r) for r in round_1}
    assert {"phase_status", "phase_commit", "attempt_model", "attempt_cost_usd",
            "attempt_confidence", "job_status", "job_accumulated_cost_usd", "job_n_phases",
            "current_commit"} <= preds
    # Story sessions record no in/out token split, no cache, no per-session test result.
    assert preds.isdisjoint({"attempt_tokens_in", "attempt_tokens_out",
                             "attempt_cache_hit_rate", "phase_test_verified"})
    # attempt_confidence emitted only for the session that records it (null-not-zero: the None
    # session must NOT emit a confidence fact).
    conf = [r for r in round_1 if _pred(r) == "attempt_confidence"]
    assert len(conf) == 1
    assert json.loads(conf[0].text)["value"] == "0.9"

    # Job facts: cell-level, all four present, ok run -> status ok.
    job = [r for r in round_1 if _pred(r).startswith("job_") or _pred(r) == "current_commit"]
    assert {_pred(r) for r in job} >= {"job_status", "job_accumulated_cost_usd", "job_n_phases",
                                       "current_commit"}
    status = next(r for r in job if _pred(r) == "job_status")
    assert json.loads(status.text)["value"] == "ok"

    # Stable ids: re-derivation over the same artifact -> byte-identical knowledge_ids.
    round_1b = kpf.derive_story_facts(REPO, REVISION, NOW)
    assert {r.knowledge_id for r in round_1b} == {r.knowledge_id for r in round_1}
    # Evidence resolution: every cited evidence_id resolves against the family evidence.
    session_ev = kpf._story_session_evidence(kpf.load_story_cells())
    result_ev = kpf._story_result_evidence(kpf.load_story_cells())
    resolve = kpf.evidence_resolver(session_ev + result_ev)
    for r in round_1:
        for eid in json.loads(r.text)["evidence_ids"]:
            assert resolve(eid) is not None, eid

    # Convergence: persist round 1, re-derive -> nothing to publish.
    _persist(kpf.REGISTRY_INDEX_PATH, *round_1)
    assert kpf.derive_story_facts(REPO, REVISION, NOW) == []


def test_story_absent_fields_stay_absent(kpf, tmp_path):
    # A session with NO confidence, NO tokens, NO error, exit 0 -> only status/model/cost/commit.
    _write_story_cell(tmp_path, "sparse", sessions=[
        {"session_number": 1, "exit_code": 0, "commit_hash": "abc", "cost_usd": 0.4},
    ])
    records = kpf.derive_story_facts(REPO, REVISION, NOW)
    attempt = [r for r in records if "attempt" in _pred(r) or _pred(r).startswith("phase_")]
    assert {_pred(r) for r in attempt} == {
        "phase_status", "phase_commit", "attempt_model", "attempt_cost_usd",
    }
    assert not any(r for r in records if "test_executed_success" in json.dumps(r.text) and _pred(r) == "phase_test_verified")
    assert not any(_pred(r) == "attempt_tokens_in" for r in records)


# ── 1b. Story token split: the census's PARTIAL rows become PRODUCED on re-derivation ──


def test_story_token_split_becomes_produced(kpf, tmp_path):
    # The backfill census named attempt_tokens_in/out PARTIAL for stories (flat total_tokens, no
    # split). With the s1 instrumentation a session that records a backend-reported split makes
    # those rows PRODUCED on re-derivation; a session without the split stays absent.
    _write_story_cell(tmp_path, "split", sessions=[
        {"session_number": 1, "exit_code": 0, "commit_hash": "aaa111",
         "cost_usd": 0.5, "tokens": {"in": 300, "out": 200}},
        {"session_number": 2, "exit_code": 0, "commit_hash": "bbb222",
         "cost_usd": 1.0, "total_tokens": 700},  # flat-only: split stays absent
        {"session_number": 3, "exit_code": 0, "commit_hash": "ccc333",
         "cost_usd": 1.5, "tokens": {"in": 0, "out": 0}},  # measured zero is a real split
    ])
    records = kpf.derive_story_facts(REPO, REVISION, NOW)

    tok_in = [r for r in records if _pred(r) == "attempt_tokens_in"]
    tok_out = [r for r in records if _pred(r) == "attempt_tokens_out"]
    # Only the two sessions whose backend reported a split emit in/out facts.
    assert len(tok_in) == 2
    assert len(tok_out) == 2
    values_in = {json.loads(r.text)["value"] for r in tok_in}
    assert values_in == {"300", "0"}  # measured 0 is emitted (null-not-zero)
    values_out = {json.loads(r.text)["value"] for r in tok_out}
    assert values_out == {"200", "0"}

    # Stable ids: re-derivation over the same artifact -> byte-identical knowledge_ids.
    round_1b = kpf.derive_story_facts(REPO, REVISION, NOW)
    assert {r.knowledge_id for r in round_1b} == {r.knowledge_id for r in records}
    _persist(kpf.REGISTRY_INDEX_PATH, *records)
    assert kpf.derive_story_facts(REPO, REVISION, NOW) == []


def test_story_per_run_identity_is_distinct(kpf, tmp_path):
    # Two cells: same story+model, DIFFERENT condition -> distinct JOB cells (no cross-supersede).
    _write_story_cell(tmp_path, "c_clean", condition="clean", sessions=[
        {"session_number": 1, "exit_code": 0, "commit_hash": "a", "cost_usd": 0.5}])
    _write_story_cell(tmp_path, "c_bad", condition="bad_seed", sessions=[
        {"session_number": 1, "exit_code": 1, "commit_hash": "b", "cost_usd": 0.7}])
    records = kpf.derive_story_facts(REPO, REVISION, NOW)
    job_cost = [r for r in records if _pred(r) == "job_accumulated_cost_usd"]
    assert len(job_cost) == 2
    assert len({r.entity_id for r in job_cost}) == 2  # clean vs bad_seed are different cells

    # Per-session attempts are run-qualified: two sessions in one cell, two distinct entities.
    sess = [r for r in records if _pred(r) == "phase_status"]
    assert len(sess) == 2
    assert len({r.entity_id for r in sess}) == 2


# ── 2. Summary derivation: attempt facts, absent fields stay absent, no job fabrication ──


def test_summary_derivation_and_absent_fields(kpf, tmp_path):
    _write_summary(tmp_path, [
        {"experiment": "exp_a", "worktree_name": "exp_a", "model": "deepseek/deepseek-v4-pro",
         "cost": 1.2, "tokens_input": 100, "tokens_output": 50},
        {"experiment": "exp_b", "worktree_name": "exp_b", "model": "openai/gpt-5.6-luna",
         "cost": 2.4},  # no tokens, no status, no commit, no confidence
    ])
    records = kpf.derive_summary_facts(REPO, REVISION, NOW)
    assert records, "summary derivation must succeed and produce facts"

    attempt = [r for r in records if _pred(r).startswith("attempt_") or _pred(r).startswith("phase_")]
    preds = {_pred(r) for r in attempt}
    assert {"attempt_model", "attempt_cost_usd"} <= preds
    # tokens only for the entry that records them (null-not-zero).
    tok_in = [r for r in attempt if _pred(r) == "attempt_tokens_in"]
    assert len(tok_in) == 1
    assert json.loads(tok_in[0].text)["value"] == "100"
    # no status/commit/confidence fabricated for entries that record none.
    assert not any(_pred(r) == "phase_status" for r in attempt)
    assert not any(_pred(r) == "phase_commit" for r in attempt)
    assert not any(_pred(r) == "attempt_confidence" for r in attempt)
    # summary is fed to attempt_facts ONLY — no job_status can be fabricated.
    assert not any(_pred(r) == "job_status" for r in records)
    assert not any(_pred(r) == "job_accumulated_cost_usd" for r in records)

    # Stable ids + convergence.
    round_1b = kpf.derive_summary_facts(REPO, REVISION, NOW)
    assert {r.knowledge_id for r in round_1b} == {r.knowledge_id for r in records}
    _persist(kpf.REGISTRY_INDEX_PATH, *records)
    assert kpf.derive_summary_facts(REPO, REVISION, NOW) == []


# ── 3. Corpus derivation: all three families in one batch ──


def test_corpus_derivation_combines_all_families(kpf, tmp_path):
    # One workflow run (the existing family) + one story cell + one summary entry.
    run_dir = tmp_path / "experiments" / "results" / "workflows" / "demo"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "20260820T000000Z.json").write_text(json.dumps({
        "spec_name": "demo", "spec_id": "demo@1.0", "model": "deepseek/deepseek-v4-pro",
        "workdir": "/tmp/x", "goal": "build it", "git_sha": "abc123",
        "started_at": NOW, "ended_at": NOW, "total_cost_usd": 1.5, "ok": True,
        "phases": [{"phase": "implement", "kind": "agent", "status": "ok",
                    "model": "deepseek/deepseek-v4-pro", "commit_hash": "abc123",
                    "tokens": {"in": 100, "out": 50}, "cost_usd": 1.5,
                    "cache_hit_rate": 0.5, "confidence": 0.9}],
    }))
    _write_story_cell(tmp_path, "s_one", sessions=[
        {"session_number": 1, "exit_code": 0, "commit_hash": "c1", "cost_usd": 0.3}])
    _write_summary(tmp_path, [
        {"experiment": "exp_c", "worktree_name": "exp_c", "model": "deepseek/deepseek-v4-pro",
         "cost": 0.9}])
    # A minimal generated spec index so the spec_status/v1 ladder rung has an entry to read.
    spec_dir = tmp_path / "experiments" / "specs"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "index.json").write_text(json.dumps({
        "schema_version": "spec-status/v1", "generated_at": NOW, "n_specs": 1,
        "specs": [{"name": "demo", "version": "0.1", "status": "completed",
                   "spec_path": "workflows/repository/demo.yaml", "n_runs": 1,
                   "last_run_at": NOW, "latest_ok": True,
                   "latest_model": "deepseek/deepseek-v4-pro", "latest_cost_usd": 1.5}],
    }))

    records = kpf.derive_corpus_facts(REPO, REVISION, NOW)
    preds = {_pred(r) for r in records}
    assert "phase_status" in preds                      # workflow + story attempts
    assert "workflow_status" in preds                   # workflow top-of-ladder
    assert "job_accumulated_cost_usd" in preds          # workflow + story jobs
    assert "attempt_cost_usd" in preds                  # workflow + story + summary attempts
    assert "spec_status" in preds                       # spec ladder rung

    # Re-derivation over the same corpus, empty registry -> byte-identical ids.
    round_1b = kpf.derive_corpus_facts(REPO, REVISION, NOW)
    assert {r.knowledge_id for r in round_1b} == {r.knowledge_id for r in records}

    # Evidence resolution for every fact across all three families. Workflow_facts/v1 cites the
    # FINALIZED lower fact knowledge_ids (the staleness-cascade backbone), not raw evidence ids,
    # so an id resolves either against the raw evidence resolver OR against another record's
    # knowledge_id in this same batch.
    resolve = kpf.evidence_resolver(
        kpf._run_evidence(kpf.load_run_jsons())
        + kpf._story_session_evidence(kpf.load_story_cells())
        + kpf._story_result_evidence(kpf.load_story_cells())
        + kpf._summary_attempt_evidence(kpf.load_summary_entries())
    )
    batch_ids = {r.knowledge_id for r in records}
    for r in records:
        for eid in json.loads(r.text)["evidence_ids"]:
            assert resolve(eid) is not None or eid in batch_ids, eid


# ── 4. Evidence identity: content-addressed, deduplicated, resolvable ──


def test_family_evidence_is_content_addressed_and_deduplicated(kpf, tmp_path):
    cell = _write_story_cell(tmp_path, "cell_a", sessions=[
        {"session_number": 1, "exit_code": 0, "commit_hash": "a", "cost_usd": 0.5}])

    session_ev = kpf._story_session_evidence(kpf.load_story_cells())
    result_ev = kpf._story_result_evidence(kpf.load_story_cells())

    assert len(session_ev) == 1
    assert len(result_ev) == 1
    assert all(isinstance(it, EvidenceItem) for it in session_ev + result_ev)
    # The evidence_id is content-addressed from the projected artifact (same formula as the
    # workflow family) — independent re-computation must agree.
    assert result_ev[0].evidence_id == f"story_result:{run_artifact_id(result_ev[0].payload)}"
    assert session_ev[0].evidence_id.startswith("story_session:")
    assert session_ev[0].payload["spec_name"] == "task_manager_api_clean"
    assert result_ev[0].payload["spec_name"] == "task_manager_api_clean"

    # A byte-identical duplicate on disk collapses to ONE evidence item (the _run_evidence guard).
    _write_story_cell(tmp_path, "cell_a_dup", condition="clean", completed_at=cell["completed_at"],
                      total_cost=cell["summary"]["total_cost"], sessions=[
        {"session_number": 1, "exit_code": 0, "commit_hash": "a", "cost_usd": 0.5}])
    assert len(kpf._story_session_evidence(kpf.load_story_cells())) == 1
    assert len(kpf._story_result_evidence(kpf.load_story_cells())) == 1
