"""Hermetic tests for the first-class story bridge — ``story_facts/v1`` (CAP story bridge, s2).

Pure-reducer tests (fixture story cells → facts; no Redis, no filesystem) plus one producer-path
test through the hermetically re-rooted ``scripts/kb_produce_facts.py`` (the sibling extension
test's pattern). Covers the workflow's VERIFY contract: story fixture → facts, re-derivation
byte-identical, absent fields stay absent — and the GUARD: every emitted fact passes
``verify_chain`` against the registered ``REDUCERS`` (the single-level discipline the module
docstring documents), and every predicate comes from ``FACT_PREDICATES``.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from agentic_dynamics.control import fact_ingestion as fi
from agentic_dynamics.control.facts import (
    Authority,
    EvidenceItem,
    ReducerInput,
    is_canonical,
    verify_chain,
)
from agentic_dynamics.control.reducers import (
    REDUCERS,
    STORY_FACTS_V1,
    get_reducer,
    story_facts_v1,
)
from agentic_dynamics.control.reducers._common import run_artifact_id
from agentic_dynamics.runtime.story.models import SessionResult, StoryResult

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO = "agentic-dynamics"
REVISION = "0123456789abcdef0123456789abcdef01234567"
NOW = "2026-08-23T00:00:00+00:00"


# ── Fixtures ────────────────────────────────────────────────────


def _cell(**overrides) -> dict:
    """A story result cell — the raw ``StoryResult.to_dict()`` shape the reducer consumes."""
    cell = {
        "story_name": "task_manager_api",
        "story_id": "cell_one",
        "model": "deepseek/deepseek-v4-pro",
        "perturbation_condition": "clean",
        "started_at": "2026-08-20T00:00:00+00:00",
        "completed_at": "2026-08-20T00:05:00+00:00",
        "error": "",
        "test_executed_success": True,
        "sessions": [
            {
                "session_number": 1,
                "exit_code": 0,
                "commit_hash": "aaa111",
                "cost_usd": 0.5,
                "confidence": 0.9,
                "tokens": {"in": 300, "out": 200},
            },
            {
                "session_number": 2,
                "exit_code": 0,
                "commit_hash": "bbb222",
                "cost_usd": 1.0,
                "confidence": 0.8,
                "tokens": {"in": 400, "out": 300},
            },
        ],
    }
    cell.update(overrides)
    return cell


def _input(*cells, now: str = NOW) -> ReducerInput:
    """One ``story`` EvidenceItem per cell, content-addressed, injected clock + revision."""
    return ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workload",
        scope_id="",
        repository_id=REPO,
        evidence=tuple(
            EvidenceItem(
                source_type="story",
                evidence_id=f"story:{run_artifact_id(c)}",
                payload=c,
            )
            for c in cells
        ),
        facts=(),
        now=now,
        source_revision=REVISION,
    )


def _by_predicate(facts):
    by: dict[str, list] = {}
    for f in facts:
        by.setdefault(f.predicate, []).append(f)
    return by


def _registration_line(record) -> dict:
    """The line ``kb_worker.py``'s ``kb-registry-v1`` handler would append for one record."""
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
    lines = "".join(json.dumps(_registration_line(r)) + "\n" for r in records)
    with registry_path.open("a") as f:
        f.write(lines)


# ── Registration ────────────────────────────────────────────────


def test_story_facts_reducer_is_registered():
    assert REDUCERS[STORY_FACTS_V1.version] is STORY_FACTS_V1
    assert STORY_FACTS_V1.name == "story_facts"
    assert STORY_FACTS_V1.version == "story_facts/v1"
    assert STORY_FACTS_V1.level == "fact"
    assert STORY_FACTS_V1.scope_type == "attempt"
    assert STORY_FACTS_V1.consumes == ("story",)
    assert callable(get_reducer("story_facts/v1"))
    # Every predicate the reducer declares exists in FACT_PREDICATES with it named as a producer.
    from agentic_dynamics.control.facts import FACT_PREDICATES

    for predicate in STORY_FACTS_V1.produces:
        assert predicate in FACT_PREDICATES
        assert "story_facts/v1" in FACT_PREDICATES[predicate].produced_by


# ── Per-session attempt facts ───────────────────────────────────


def test_story_facts_emit_per_session_attempt_facts():
    facts = story_facts_v1(_input(_cell()))
    by = _by_predicate(facts)

    assert len(by["phase_status"]) == 2
    assert {f.subject_id for f in by["phase_status"]} == {"session1", "session2"}
    assert {f.value for f in by["phase_status"]} == {"ok"}

    assert {f.value for f in by["attempt_model"]} == {"deepseek/deepseek-v4-pro"}
    assert {f.value for f in by["attempt_cost_usd"]} == {"0.5", "1.0"}
    assert {f.value for f in by["attempt_confidence"]} == {"0.9", "0.8"}
    assert {f.value for f in by["phase_commit"]} == {"aaa111", "bbb222"}
    assert {f.value for f in by["attempt_tokens_in"]} == {"300", "400"}
    assert {f.value for f in by["attempt_tokens_out"]} == {"200", "300"}

    # The cell-level test outcome attaches to the TERMINAL session only.
    assert len(by["phase_test_verified"]) == 1
    assert by["phase_test_verified"][0].subject_id == "session2"
    assert by["phase_test_verified"][0].value == "true"


def test_story_fact_scope_is_job_qualified_and_run_qualified():
    cell = _cell()
    run_id = run_artifact_id(_session_run_of(cell, cell["sessions"][0]))
    facts = story_facts_v1(_input(cell))
    status = _by_predicate(facts)["phase_status"][0]
    cell_slug = "wf_task_manager_api_clean_deepseek_deepseek_v4_pro"
    assert status.scope_type == "attempt"
    assert status.scope_id == f"{cell_slug}:session1:{run_id}"
    assert status.scope_path == (
        f"org:{REPO}/workload:task_manager_api_clean/job:{cell_slug}"
        f"/attempt:session1/run:{run_id}"
    )
    assert status.subject_type == "attempt"
    assert status.subject_id == "session1"


def _session_run_of(cell, session) -> dict:
    """Recompute the single-phase run dict the reducer's identity anchors on (module-private
    helper mirror) — verifies the scope_id the reducer derives, independent of the reducer."""
    spec_name = f"{cell['story_name']}_{cell['perturbation_condition']}"
    commit = str(session.get("commit_hash") or "")
    phase = {"phase": "session1", "kind": "agent"}
    phase["status"] = "ok" if session.get("exit_code") == 0 and not session.get("error") else "failed"
    if commit:
        phase["commit_hash"] = commit
    phase["model"] = cell["model"]
    if isinstance(session.get("cost_usd"), (int, float)):
        phase["cost_usd"] = session["cost_usd"]
    if session.get("confidence") is not None:
        phase["confidence"] = session["confidence"]
    split = {"in": session.get("tokens", {}).get("in"), "out": session.get("tokens", {}).get("out")}
    if split["in"] is not None or split["out"] is not None:
        phase["tokens"] = split
    return {
        "spec_name": spec_name,
        "spec_id": f"{spec_name}@story",
        "model": cell["model"],
        "git_sha": commit,
        "started_at": cell["started_at"],
        "ended_at": cell["completed_at"],
        "total_cost_usd": None,
        "ok": True,
        "phases": [phase],
    }


def test_story_fact_epistemics_follow_the_design():
    by = _by_predicate(story_facts_v1(_input(_cell())))
    assert by["attempt_cost_usd"][0].epistemic_status == "observed"
    assert by["attempt_cost_usd"][0].authority is Authority.MEASURED
    assert by["attempt_cost_usd"][0].evidence_class == "[M]"
    assert by["attempt_confidence"][0].epistemic_status == "advisory"
    assert by["attempt_confidence"][0].authority is Authority.ADVISORY
    assert by["attempt_confidence"][0].evidence_class == "[H]"
    assert by["phase_test_verified"][0].epistemic_status == "verified"
    assert by["phase_test_verified"][0].authority is Authority.MEASURED
    # advisory confidence is stored but never canonical — the design §5 flag.
    assert not is_canonical(by["attempt_confidence"][0])


# ── Absent stays absent (null-not-zero) ─────────────────────────


def test_absent_fields_stay_absent():
    # A session with no confidence, no tokens, no commit, and a cell with NO test verdict.
    cell = _cell(test_executed_success=None, sessions=[
        {"session_number": 1, "exit_code": 0, "cost_usd": 0.4},
    ])
    preds = {f.predicate for f in story_facts_v1(_input(cell))}
    assert preds == {"phase_status", "attempt_model", "attempt_cost_usd"}
    # confidence/tokens/commit/test-verified are absent — never a defaulted 0/false.
    assert preds.isdisjoint(
        {"attempt_confidence", "attempt_tokens_in", "attempt_tokens_out",
         "phase_commit", "phase_test_verified"}
    )


def test_measured_zero_split_is_a_real_split_absent_is_not():
    cell = _cell(
        test_executed_success=None,
        sessions=[
            {"session_number": 1, "exit_code": 0, "commit_hash": "a",
             "cost_usd": 0.5, "tokens": {"in": 0, "out": 0}},  # measured zero IS a split
            {"session_number": 2, "exit_code": 0, "commit_hash": "b",
             "cost_usd": 1.0, "total_tokens": 700},  # flat-only: split stays absent
        ],
    )
    facts = story_facts_v1(_input(cell))
    by = _by_predicate(facts)
    assert {f.value for f in by["attempt_tokens_in"]} == {"0"}
    assert {f.value for f in by["attempt_tokens_out"]} == {"0"}
    assert len(by["attempt_tokens_in"]) == 1  # only the measured-zero session
    assert len(by["attempt_tokens_out"]) == 1


def test_phase_test_verified_is_absent_when_cell_verdict_is_none():
    cell = _cell(test_executed_success=None)
    preds = {f.predicate for f in story_facts_v1(_input(cell))}
    assert "phase_test_verified" not in preds


def test_failed_session_records_status_failed():
    cell = _cell(sessions=[
        {"session_number": 1, "exit_code": 1, "error": "timeout", "commit_hash": "a",
         "cost_usd": 0.5},
    ])
    status = _by_predicate(story_facts_v1(_input(cell)))["phase_status"][0]
    assert status.value == "failed"


# ── Identity: stable, time-invariant, per-run distinct ──────────


def test_rederivation_is_byte_identical_and_time_invariant():
    cell = _cell()
    first = _by_predicate(story_facts_v1(_input(cell)))["attempt_cost_usd"][0]
    # Different injected clock, same artifact -> identical identity and record bytes.
    second = _by_predicate(story_facts_v1(_input(cell, now="2027-01-01T00:00:00+00:00")))
    second = second["attempt_cost_usd"][0]
    assert first.fact_entity_id == second.fact_entity_id
    assert fi.build_fact_record(first).knowledge_id == fi.build_fact_record(second).knowledge_id
    assert first.observed_at == second.observed_at  # clock is only the fallback, never the value


def test_two_distinct_cells_never_collide_on_attempt_entity_id():
    # Same story+model, DIFFERENT condition -> distinct cells -> distinct attempt entity ids.
    cell_a = _cell(perturbation_condition="clean")
    cell_b = _cell(perturbation_condition="bad_seed")
    facts_a = _by_predicate(story_facts_v1(_input(cell_a)))["attempt_cost_usd"][0]
    facts_b = _by_predicate(story_facts_v1(_input(cell_b)))["attempt_cost_usd"][0]
    assert facts_a.fact_entity_id != facts_b.fact_entity_id

    # Two distinct cells, same condition, distinct started_at -> distinct run artifacts -> distinct
    # attempt identities (the CAP I0-I3 per-run invariant, story-family version).
    cell_a = _cell(started_at="2026-08-20T00:00:00+00:00")
    cell_b = _cell(started_at="2026-08-22T00:00:00+00:00")
    a = _by_predicate(story_facts_v1(_input(cell_a)))["attempt_cost_usd"][0]
    b = _by_predicate(story_facts_v1(_input(cell_b)))["attempt_cost_usd"][0]
    assert a.fact_entity_id != b.fact_entity_id


# ── verify_chain (the GUARD's architectural claim) ──────────────


def test_every_emitted_fact_passes_verify_chain():
    facts = story_facts_v1(_input(_cell(), _cell(perturbation_condition="bad_seed")))
    resolve = {
        f"story:{run_artifact_id(_cell())}": _cell(),
        f"story:{run_artifact_id(_cell(perturbation_condition='bad_seed'))}": _cell(
            perturbation_condition="bad_seed"
        ),
    }.get
    for fact in facts:
        finalized = fi.finalize_fact(fact, fi.build_fact_record(fact))
        assert verify_chain(finalized, REDUCERS, resolve=resolve) == []


# ── Consuming a real StoryResult object (the contract) ──────────


def test_reducer_consumes_a_real_story_result_object():
    result = StoryResult(
        story_name="task_manager_api",
        story_id="cell_obj",
        model="deepseek/deepseek-v4-pro",
        perturbation_condition="clean",
        started_at="2026-08-20T00:00:00+00:00",
        completed_at="2026-08-20T00:05:00+00:00",
        test_executed_success=True,
        sessions=[
            SessionResult(1, "greenfield", "Build.", commit_hash="aaa111",
                          cost_usd=0.5, confidence=0.9, tokens={"in": 300, "out": 200}),
        ],
    )
    facts = story_facts_v1(_input(result.to_dict()))
    by = _by_predicate(facts)
    assert by["phase_test_verified"][0].value == "true"
    assert by["attempt_tokens_in"][0].value == "300"


# ── Producer path (hermetically re-rooted kb_produce_facts) ─────


def _load_kb_produce_facts():
    spec = importlib.util.spec_from_file_location(
        "kb_produce_facts_story_reducer_under_test",
        PROJECT_ROOT / "scripts" / "kb_produce_facts.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_cell(tmp_path: Path, filename: str, **overrides) -> dict:
    cell = _cell(story_id=filename, **overrides)
    out_dir = tmp_path / "experiments" / "results" / "stories"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{filename}.json").write_text(json.dumps(cell))
    return cell


@pytest.fixture
def kpf(tmp_path, monkeypatch):
    module = _load_kb_produce_facts()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    return module


def test_producer_path_derives_first_class_story_facts(kpf, tmp_path):
    _write_cell(tmp_path, "cell_one", sessions=[
        {"session_number": 1, "exit_code": 0, "commit_hash": "aaa111",
         "cost_usd": 0.5, "confidence": 0.9, "tokens": {"in": 300, "out": 200}},
        {"session_number": 2, "exit_code": 0, "commit_hash": "bbb222",
         "cost_usd": 1.0, "confidence": 0.8},
    ])

    records = kpf.derive_story_facts_v1(REPO, REVISION, NOW)
    assert records, "story_facts/v1 derivation must succeed and produce records"
    assert all(r.extractor_version == "story_facts/v1" for r in records)
    assert all(r.supersedes is None for r in records)  # empty registry -> all first versions

    preds = {json.loads(r.text)["predicate"] for r in records}
    assert {"phase_status", "phase_commit", "attempt_model", "attempt_cost_usd",
            "attempt_confidence", "attempt_tokens_in", "attempt_tokens_out",
            "phase_test_verified"} <= preds
    # phase_test_verified emitted exactly once (the terminal session), from the cell-level verdict.
    verified = [r for r in records if json.loads(r.text)["predicate"] == "phase_test_verified"]
    assert len(verified) == 1
    assert json.loads(verified[0].text)["value"] == "true"

    # Re-derivation over the same artifact -> byte-identical knowledge_ids; converge to [] after
    # persisting (the idempotence contract, exactly like the p3 extension tests).
    round_1b = kpf.derive_story_facts_v1(REPO, REVISION, NOW)
    assert {r.knowledge_id for r in round_1b} == {r.knowledge_id for r in records}
    _persist(kpf.REGISTRY_INDEX_PATH, *records)
    assert kpf.derive_story_facts_v1(REPO, REVISION, NOW) == []


def test_producer_story_facts_v1_supersedes_the_projection_slot(kpf, tmp_path):
    # Same session -> the projection (attempt_facts/v1) and story_facts/v1 agree on the logical
    # slot (same scope_id/predicate/subject), so emission under the new reducer_version replaces
    # the adaptation fact rather than coexisting with it (the bridge's supersede-on-emission).
    _write_cell(tmp_path, "slot", sessions=[
        {"session_number": 1, "exit_code": 0, "commit_hash": "aaa111", "cost_usd": 0.5},
    ])

    projection = kpf.derive_story_facts(REPO, REVISION, NOW)
    bridge = kpf.derive_story_facts_v1(REPO, REVISION, NOW)

    def slot_of(record) -> str:
        return record.entity_id

    proj_cost = next(r for r in projection if json.loads(r.text)["predicate"] == "attempt_cost_usd")
    bridge_cost = next(r for r in bridge if json.loads(r.text)["predicate"] == "attempt_cost_usd")
    # Same fact_entity_id (the logical slot), different reducer_version -> different record ids.
    assert slot_of(proj_cost) == slot_of(bridge_cost)
    assert proj_cost.knowledge_id != bridge_cost.knowledge_id
    assert bridge_cost.extractor_version == "story_facts/v1"
    assert json.loads(bridge_cost.text)["reducer_version"] == "story_facts/v1"
