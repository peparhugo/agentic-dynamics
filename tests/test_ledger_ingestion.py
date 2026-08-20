"""Tests for ledger ingestion (ledger_ingestion).

Covers the extractor contract constants, the two record kinds (``ledger_job`` +
``ledger_attempt``) per cell, MEASURED/[M] provenance, the reused artifact/event
contract, and — the two base-inventory gaps this module exists to close — gap (a)'s
no-session fallback (Finding 4) and gap (b)'s ``meta_*`` classification (Finding 5).
"""

import hashlib

import pytest

from instrument import ledger_ingestion as li
from instrument.knowledge import Authority
from instrument.knowledge_ingestion import record_to_artifact


def _story_result(**overrides) -> dict:
    base = {
        "story_name": "task_manager_api",
        "story_id": "abc123def456",
        "language": "python",
        "model": "deepseek/deepseek-v4-flash",
        "worktree": "/tmp/pipeline/story_abc123",
        "started_at": "2026-08-15T00:00:00+00:00",
        "completed_at": "2026-08-15T00:05:00+00:00",
        "perturbation_strength": 0.0,
        "test_executed_success": True,
        "summary": {"total_cost": 2.5, "total_tokens": 12000},
        "sessions": [
            {
                "session_number": 1,
                "task_type": "greenfield",
                "commit_hash": "commit_s1",
                # The exact 15-field agentic shape story.py:261-279 writes (trimmed to
                # the fields this producer reads plus a few neighbors for realism).
                "agentic": {
                    "tests_passed": 8,
                    "tests_total": 8,
                    "tool_calls": 40,
                    "retries": 0,
                    "depth": 3,
                    "files_created": 5,
                    "prompt_tokens": 4000,
                    "completion_tokens": 1200,
                    "reasoning_tokens": 300,
                    "answer_tokens": 900,
                    "explanation_tokens": 300,
                    "total_tokens": 5200,
                    "estimated_cost_usd": 0.42,
                    "cache_read_tokens": 100,
                    "cache_write_tokens": 50,
                    "confidence": 0.81,
                },
            },
        ],
    }
    base.update(overrides)
    return base


def _opencode_session_row(**overrides) -> dict:
    base = {
        "id": "sess_db_1",
        "directory": "/tmp/pipeline/story_abc123",
        "title": "flask_api_std_1",
        "cost": 0.5,
        "tokens_input": 4000,
        "tokens_output": 1200,
        "tokens_reasoning": 300,
        "tokens_cache_read": 100,
        "tokens_cache_write": 50,
        "provider": "deepseek",
        "model_id": "deepseek-v4-flash",
        "time_created": 1234567890,
    }
    base.update(overrides)
    return base


# ── Extractor contract constants ────────────────────────────────


def test_extractor_constants():
    assert li.EXTRACTOR_VERSION == "ledger/v1"
    assert li.FALLBACK_EXTRACTOR_VERSION == "ledger/v1-storyfallback"
    assert li.SOURCE_TYPE_JOB == "ledger_job"
    assert li.SOURCE_TYPE_ATTEMPT == "ledger_attempt"
    assert li.SOURCE_TYPE_META == "meta_session"


# ── classify_session (gap b) ─────────────────────────────────────


def test_classify_session_routes_meta_batch_star_to_meta_session():
    # Literal regression test for the meta_batch_* false-match
    # docs/canonical_state_base_verify.md documented: "batch" is itself one of the
    # EXPERIMENT_SESSION_PATTERNS substrings, so a naive substring match would have
    # folded this meta-analysis session into "ledger_attempt" cost rollups.
    assert li.classify_session("meta_batch_042") == "meta_session"


def test_classify_session_routes_bare_meta_prefix_to_meta_session():
    assert li.classify_session("meta_review_pass") == "meta_session"


def test_classify_session_still_matches_real_experiment_titles():
    # Negative case — guards against over-broadening the meta_ prefix check into
    # swallowing genuine experiment titles that merely contain "meta" as a substring
    # elsewhere, or any real experiment-pattern title in general.
    assert li.classify_session("flask_api_std_1") == "ledger_attempt"
    assert li.classify_session("std_batch_sweep_3") == "ledger_attempt"


def test_classify_session_unclassified_title_still_registers():
    # Round 1 OQ1, unchanged: an ambiguous title is not silently dropped.
    assert li.classify_session("totally_unrelated_thing") == "ledger_attempt"


def test_experiment_session_patterns_live_in_instrument_not_scripts():
    # The dependency edge is now scripts -> src, not the reverse: `_constants.py`
    # imports EXPERIMENT_SESSION_PATTERNS from instrument.session_types (the single
    # source of truth) instead of being exec'd back into the package at import time.
    # Loading _constants.py by path must therefore yield the SAME list object the
    # instrument exports — a re-declared copy in scripts/ would be a regression.
    import importlib.util
    from pathlib import Path

    from instrument import session_types as st

    path = Path(st.__file__).resolve().parents[3] / "scripts" / "_constants.py"
    spec = importlib.util.spec_from_file_location("_check_constants", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.EXPERIMENT_SESSION_PATTERNS is st.EXPERIMENT_SESSION_PATTERNS
    assert module.normalize_task is st.normalize_task


# ── Baseline path: DB row present ────────────────────────────────


def test_derive_ledger_records_uses_db_join_when_session_row_present():
    records = li.derive_ledger_records(_story_result(), _opencode_session_row(), {})
    job = next(r for r in records if r.source_type == "ledger_job")
    assert job.extractor_version == "ledger/v1"
    assert "deepseek/deepseek-v4-flash" in job.text
    assert "0.5" in job.text  # opencode_session_row's own cost, not the summary's


def test_derive_ledger_records_returns_one_job_plus_one_attempt_per_session():
    records = li.derive_ledger_records(_story_result(), _opencode_session_row(), {})
    assert len(records) == 2
    assert [r.source_type for r in records] == ["ledger_job", "ledger_attempt"]


# ── Gap (a): no-session fallback ─────────────────────────────────


def test_derive_ledger_records_falls_back_to_agentic_block_when_session_row_none():
    story_result = _story_result()
    records = li.derive_ledger_records(story_result, None, {})
    job = next(r for r in records if r.source_type in ("ledger_job",))
    attempt = next(r for r in records if r.source_type == "ledger_attempt")
    agentic = story_result["sessions"][0]["agentic"]

    assert job.extractor_version == "ledger/v1-storyfallback"
    assert attempt.extractor_version == "ledger/v1-storyfallback"
    # Tokens/cost/confidence match the session's own agentic block — every field the DB
    # join would have supplied is already there (story.py's SessionResult.agentic is
    # backend-agnostic).
    assert attempt.confidence == agentic["confidence"]
    assert str(agentic["total_tokens"]) in attempt.text
    assert str(agentic["estimated_cost_usd"]) in attempt.text


def test_job_falls_back_to_story_summary_when_session_row_none():
    story_result = _story_result()
    records = li.derive_ledger_records(story_result, None, {})
    job = next(r for r in records if r.source_type == "ledger_job")
    summary = story_result["summary"]
    assert str(summary["total_cost"]) in job.text
    assert str(summary["total_tokens"]) in job.text


# ── Provenance ───────────────────────────────────────────────────


def test_job_authority_is_measured_and_m():
    records = li.derive_ledger_records(_story_result(), _opencode_session_row(), {})
    job = next(r for r in records if r.source_type == "ledger_job")
    assert job.authority is Authority.MEASURED
    assert job.evidence_class == "[M]"


def test_meta_session_authority_is_advisory_and_h():
    story_result = _story_result()
    row = _opencode_session_row(title="meta_batch_099")
    records = li.derive_ledger_records(story_result, row, {})
    attempt = next(r for r in records if r.source_type == "meta_session")
    assert attempt.authority is Authority.ADVISORY
    assert attempt.evidence_class == "[H]"


def test_meta_title_routes_the_attempt_to_meta_session_not_ledger_attempt():
    story_result = _story_result()
    row = _opencode_session_row(title="meta_batch_099")
    records = li.derive_ledger_records(story_result, row, {})
    source_types = {r.source_type for r in records}
    assert "meta_session" in source_types
    assert "ledger_attempt" not in source_types


# ── Reused artifact/event contract ──────────────────────────────


def test_content_hash_equals_sha256_of_record_to_artifact():
    records = li.derive_ledger_records(_story_result(), _opencode_session_row(), {})
    for record in records:
        assert record.content_hash == hashlib.sha256(record_to_artifact(record)).hexdigest()


# ── Errors / batch pre-filter ────────────────────────────────────


def test_build_job_record_raises_without_story_id():
    with pytest.raises(ValueError):
        li.build_job_record(_story_result(story_id=""), _opencode_session_row(), {})


def test_derive_ledger_records_skips_missing_story_id_instead_of_raising():
    assert li.derive_ledger_records(_story_result(story_id=""), _opencode_session_row(), {}) == []
