"""Tests for the shared record-builder factory (record_factory).

The factory is the single owner of the content-hash back-fill ordering (blank derived ids +
volatile timestamps → serialize → hash → back-fill) that was previously copy-pasted into all
nine producer modules. These tests prove two things: (1) the factory reproduces the canonical
identity contract from :mod:`instrument.knowledge`, and (2) — the load-bearing regression guard —
every producer's ``knowledge_id`` is **byte-identical** to the value the pre-refactor nine-copy
builders produced (no re-keying), via golden strings captured before the R1 refactor.
"""

import hashlib
import json
from datetime import datetime, timezone

import pytest

from instrument import code_ingestion as ci
from instrument import knowledge_ingestion as ki
from instrument import ledger_ingestion as li
from instrument import observation_ingestion as oi
from instrument import policy_ingestion as pi
from instrument import quality_ingestion as qi
from instrument import record_factory as rf
from instrument import review_ingestion as ri
from instrument import story_ingestion as si
from instrument import actuation_ingestion as ai
from instrument.knowledge import (
    Authority,
    KnowledgeRecord,
    compute_entity_id,
    compute_knowledge_id,
)

#: The pinned producer clock used for every golden capture. All golden values below were
#: recorded against the pre-refactor code with this exact ``now``; the factory must reproduce
#: them byte-for-byte.
NOW = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)


# ── The factory itself ──────────────────────────────────────────


def test_build_record_reproduces_canonical_identity():
    record = rf.build_record(
        source_type="code",
        source_uri="file://src/a.py#f",
        logical_locator="src/a.py",
        repository_id="repo-1",
        revision="abc1234",
        authority=Authority.SOURCE,
        evidence_class="[C]",
        text="f(x) — does a thing",
        extra_fields={"extractor_version": "code/v1", "symbols": ["f"]},
        now=NOW,
    )
    # entity_id is the canonical sha256(repository_id | source_uri | logical_locator) ...
    assert record.entity_id == compute_entity_id("repo-1", "file://src/a.py#f", "src/a.py")
    # ... content_hash is the sha256 of the durable artifact ...
    assert record.content_hash == hashlib.sha256(rf.record_to_artifact(record)).hexdigest()
    # ... and knowledge_id folds entity_id | revision | content_hash | extractor_version.
    assert record.knowledge_id == compute_knowledge_id(
        record.entity_id, "abc1234", record.content_hash, "code/v1"
    )


def test_build_record_commit_sha_defaults_to_revision():
    record = rf.build_record(
        source_type="story",
        source_uri="story:s1",
        logical_locator="s1",
        repository_id="repo",
        revision="deadbeef",
        authority=Authority.MEASURED,
        evidence_class="[M]",
        text="t",
        extra_fields={"extractor_version": "story/v1"},
        now=NOW,
    )
    assert record.commit_sha == "deadbeef"


def test_build_record_commit_sha_overridable_via_extra_fields():
    # review/observation/flag/actuation carry no commit but fold a REVISION_FALLBACK marker.
    record = rf.build_record(
        source_type="review",
        source_uri="review:s1",
        logical_locator="s1",
        repository_id="repo",
        revision="review/unrevisioned",
        authority=Authority.ADVISORY,
        evidence_class="[H]",
        text="t",
        extra_fields={"extractor_version": "review/v1", "commit_sha": ""},
        now=NOW,
    )
    assert record.commit_sha == ""
    # ... but knowledge_id still folds the REVISION_FALLBACK marker (the `revision` arg).
    assert compute_knowledge_id(
        record.entity_id, "review/unrevisioned", record.content_hash, "review/v1"
    ) == record.knowledge_id


def test_build_record_rejects_unknown_extra_fields():
    with pytest.raises(ValueError):
        rf.build_record(
            source_type="story",
            source_uri="story:s1",
            logical_locator="s1",
            repository_id="repo",
            revision="r",
            authority=Authority.MEASURED,
            evidence_class="[M]",
            text="t",
            extra_fields={"extractor_version": "story/v1", "not_a_real_field": 1},
            now=NOW,
        )


def test_record_to_artifact_blanks_the_five_volatile_fields():
    record = rf.build_record(
        source_type="code",
        source_uri="file://src/a.py#f",
        logical_locator="src/a.py",
        repository_id="repo",
        revision="abc1234",
        authority=Authority.SOURCE,
        evidence_class="[C]",
        text="f(x)",
        extra_fields={"extractor_version": "code/v1"},
        now=NOW,
    )
    artifact = json.loads(rf.record_to_artifact(record).decode("utf-8"))
    # The five non-content fields are blanked so content_hash is a pure function of stable
    # content — the exact blanking rule the pre-refactor record_to_artifact enforced.
    assert artifact["knowledge_id"] == ""
    assert artifact["content_hash"] == ""
    assert artifact["valid_from"] == ""
    assert artifact["observed_at"] == ""
    assert artifact["indexed_at"] == ""
    # entity_id is NOT blanked (it is derived from stable inputs, not self-referential).
    assert artifact["entity_id"] == record.entity_id


# ── Byte-identity: no re-key across the R1 refactor ─────────────


def test_finding_knowledge_id_is_byte_identical_to_pre_refactor():
    entry = {
        "worktree_name": "exp_05ngi4l9",
        "run_id": "exp_05ngi4l9",
        "model": "deepseek/deepseek-v4-pro",
        "operator": "perturbed",
        "perturbation_class": "semantic",
        "strategy": "exploratory",
        "correctness": 0.8,
        "cost": 0.033537746,
        "escape": 0.7486509085783121,
        "flail": 0.62,
        "narration_failure": False,
        "test_executed_success": None,
        "confidence": None,
        "perturbation_strength": None,
        "outcome_id": "",
    }
    assert ki.build_record(entry, now=NOW).knowledge_id == (
        "efd7a9459665b6b71a03dd24c31a5bff4a398792929d53dded63824f5b8fedc3"
    )


def _story_result() -> dict:
    return {
        "story_name": "task_manager_api",
        "story_id": "abc123def456",
        "codebase_path": "experiments/codebases/task_manager_api",
        "language": "python",
        "model": "deepseek/deepseek-v4-flash",
        "mutation_id": "",
        "perturbation_condition": "clean",
        "started_at": "2026-08-15T00:00:00+00:00",
        "completed_at": "2026-08-15T00:05:00+00:00",
        "worktree": "/tmp/pipeline/story_abc123",
        "error": "",
        "perturbation_strength": 0.0,
        "test_executed_success": True,
        "summary": {"total_cost": 1.2345, "session_count": 2, "all_successful": True},
        "sessions": [
            {"session_number": 1, "task_type": "greenfield", "prompt": "build the API",
             "commit_hash": "commit_s1", "agentic": {"confidence": 0.8}},
            {"session_number": 2, "task_type": "feature_addition", "prompt": "add auth",
             "commit_hash": "commit_s2", "agentic": {"confidence": 0.6}},
        ],
    }


def test_story_knowledge_id_is_byte_identical_to_pre_refactor():
    assert si.build_story_record(_story_result(), now=NOW).knowledge_id == (
        "aca6dac519ce74f029582f25bc34a7372eaa12620c95eab82a4071ecc8025282"
    )


def _review() -> dict:
    return {
        "story_name": "task_manager_api",
        "story_id": "abc123def456",
        "model": "deepseek/deepseek-v4-flash",
        "commit_reviews": [
            {"commit_hash": "commit_s1", "reviewer_model": "deepseek/deepseek-v4-flash",
             "architectural_fit": 0.9, "convention_adherence": 0.85, "introduces_technical_debt": False,
             "respects_existing_patterns": True, "better_or_worse": "better", "problems": [],
             "strengths": ["clean separation of concerns"], "summary": "solid incremental commit",
             "session_number": 1},
            {"commit_hash": "commit_s2", "reviewer_model": "deepseek/deepseek-v4-flash",
             "architectural_fit": 0.4, "convention_adherence": 0.5, "introduces_technical_debt": True,
             "respects_existing_patterns": False, "better_or_worse": "worse",
             "problems": [{"category": "architecture", "severity": "major", "description": "coupling"}],
             "strengths": [], "summary": "introduced tight coupling", "session_number": 2},
        ],
        "story_review": {"story_name": "task_manager_api",
             "reviewer_model": "deepseek/deepseek-v4-flash", "overall_coherence": 0.7,
             "compounding_issues": ["coupling introduced in session 2"], "key_decisions": [],
             "trajectory_description": "", "summary": "mostly coherent with a late regression"},
    }


def test_review_knowledge_id_is_byte_identical_to_pre_refactor():
    assert ri.build_review_record(_review(), now=NOW).knowledge_id == (
        "f093db7bd95c380a688860367cfda4850292f291d7cf9b87fe33066720f7bebc"
    )


def _ledger_inputs() -> tuple[dict, dict]:
    story_result = {
        "story_name": "task_manager_api", "story_id": "abc123def456", "language": "python",
        "model": "deepseek/deepseek-v4-flash", "worktree": "/tmp/pipeline/story_abc123",
        "started_at": "2026-08-15T00:00:00+00:00", "completed_at": "2026-08-15T00:05:00+00:00",
        "perturbation_strength": 0.0, "test_executed_success": True,
        "summary": {"total_cost": 2.5, "total_tokens": 12000},
        "sessions": [{"session_number": 1, "task_type": "greenfield", "commit_hash": "commit_s1",
            "agentic": {"tests_passed": 8, "tests_total": 8, "tool_calls": 40, "retries": 0,
                "depth": 3, "files_created": 5, "prompt_tokens": 4000, "completion_tokens": 1200,
                "reasoning_tokens": 300, "answer_tokens": 900, "explanation_tokens": 300,
                "total_tokens": 5200, "estimated_cost_usd": 0.42, "cache_read_tokens": 100,
                "cache_write_tokens": 50, "confidence": 0.81}}],
    }
    row = {"id": "sess_db_1", "directory": "/tmp/pipeline/story_abc123", "title": "flask_api_std_1",
           "cost": 0.5, "tokens_input": 4000, "tokens_output": 1200, "tokens_reasoning": 300,
           "tokens_cache_read": 100, "tokens_cache_write": 50, "provider": "deepseek",
           "model_id": "deepseek-v4-flash", "time_created": 1234567890}
    return story_result, row


def test_ledger_knowledge_ids_are_byte_identical_to_pre_refactor():
    story_result, row = _ledger_inputs()
    records = li.derive_ledger_records(story_result, row, {}, now=NOW)
    assert [r.knowledge_id for r in records] == [
        "df1b13f1efa4a33f3bf2103b3e0872cddb395de9428a8bff8fb62388b10eb6fd",  # ledger_job
        "d0aa8e680312606eee6d136e0ff832379f7d89a9dd40c9b3c6ce671ba65be642",  # ledger_attempt
    ]


def test_observation_knowledge_id_is_byte_identical_to_pre_refactor():
    verdict = {"cell_id": "wf_task_manager_api_1", "status": "healthy",
               "why": "on track, tests passing", "model": "deepseek/deepseek-v4-flash",
               "at": "2026-08-15T00:00:00+00:00"}
    assert oi.derive_observation_record(verdict, now=NOW).knowledge_id == (
        "635843376b6b02b5c7ef87640581e8699a422022c5287f1111044a9271085764"
    )


def test_flag_knowledge_id_is_byte_identical_to_pre_refactor():
    flag = {"at": "2026-08-15T00:00:00+00:00", "session_id": "sess_abc123",
            "title": "wf_task_manager_api_1", "model": "deepseek/deepseek-v4-flash",
            "status": "off_track", "why": "diverged from spec"}
    assert oi.derive_flag_record(flag, now=NOW).knowledge_id == (
        "95e1e940d89959f60797b54daebc2c0b2ad28baa70c15fc363594a1cf935a5ea"
    )


def test_actuation_knowledge_id_is_byte_identical_to_pre_refactor():
    candidate = {"actuation_kind": "steer", "target_session_id": "sess_abc123",
                 "target_cell_id": "wf_task_manager_api_1",
                 "requested_action": {"note": "nudge back toward the spec"},
                 "requested_by": "supervisor", "causes": "obs_knowledge_id_0001"}
    assert ai.derive_actuation_record(candidate, now=NOW).knowledge_id == (
        "8f90827115d4b7c04a24414c558f8920e08a7047f9f23587997b25b3731512b8"
    )


def test_code_knowledge_id_is_byte_identical_to_pre_refactor():
    record = ci.build_code_record(
        ci._CodeSymbol(name="add", kind="function", signature="add(a: int, b: int)",
                       docstring_head="Return the sum of a and b."),
        "math_utils.py", "python", repository_id="test-repo", revision="abc1234", now=NOW,
    )
    assert record.knowledge_id == "1e5c61e6baff71edc97c750f5b0bb277b4cf50ea75b066c3ecaf49e27672678a"


def test_policy_knowledge_id_is_byte_identical_to_pre_refactor():
    record = pi.build_policy_record(
        "AGENTS.md", "# Rules for this project", repository_id="test-repo",
        revision="abc1234", now=NOW,
    )
    assert record.knowledge_id == "404e3312eeb4b3807b38aae5e1e6c891219c04a733db210058f0a6129469bc23"


def test_quality_knowledge_id_is_byte_identical_to_pre_refactor():
    record = qi.build_quality_record(
        signal="sonar", logical_locator="/fixed/codebase/pkg", language="python",
        text="pkg: 3 bugs, 12 smells, maintainability C",
        authority=Authority.MEASURED, evidence_class="[M]",
        repository_id="test-repo", revision="abc1234", now=NOW,
    )
    assert record.knowledge_id == "eb36c38025ee70988f20e851ebd6d0e69fb20f204c9b7f6d7b2d25699a181324"
