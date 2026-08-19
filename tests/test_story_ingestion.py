"""Tests for story ingestion (story_ingestion).

Covers the extractor contract constants, identity derivation (entity_id keyed by the
logical ``story:{story_id}`` marker — not a filesystem path — so a byte-identical story
replayed from a different worktree converges on the same entity), the reused
artifact/event contract, determinism (repeated calls on the same story_result yield the
same knowledge_id; a changed body yields a different one), the MEASURED/[M] provenance,
and the batch-derivation pre-filter for a story with no story_id.
"""

from instrument import story_ingestion as si
from instrument.knowledge import Authority, compute_entity_id
from instrument.knowledge_ingestion import record_to_artifact


def _story_result(**overrides) -> dict:
    base = {
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
        "summary": {
            "total_cost": 1.2345,
            "session_count": 2,
            "all_successful": True,
        },
        "sessions": [
            {
                "session_number": 1,
                "task_type": "greenfield",
                "prompt": "build the API",
                "commit_hash": "commit_s1",
                "agentic": {"confidence": 0.8},
            },
            {
                "session_number": 2,
                "task_type": "feature_addition",
                "prompt": "add auth",
                "commit_hash": "commit_s2",
                "agentic": {"confidence": 0.6},
            },
        ],
    }
    base.update(overrides)
    return base


# ── Extractor contract constants ────────────────────────────────


def test_extractor_constants():
    assert si.EXTRACTOR_VERSION == "story/v1"
    assert si.SOURCE_TYPE == "story"
    assert si.ACL_SCOPE == "public"


# ── Identity: worktree-independent, keyed by story_id ───────────


def test_entity_id_is_a_logical_marker_not_a_filesystem_path():
    record = si.build_story_record(_story_result())
    assert record.source_uri == "story:abc123def456"
    expected = compute_entity_id("agentic-dynamics", "story:abc123def456", "abc123def456")
    assert record.entity_id == expected


def test_entity_id_converges_across_different_worktrees():
    # Finding-1-style stranding: the SAME story replayed from two different worktree
    # paths must converge on the same entity_id — the identity hashes story_id, never
    # the worktree filesystem path.
    a = si.build_story_record(_story_result(worktree="/tmp/pipeline/worktree_one"))
    b = si.build_story_record(_story_result(worktree="/tmp/pipeline/worktree_two"))
    assert a.entity_id == b.entity_id


def test_logical_locator_is_story_id():
    record = si.build_story_record(_story_result())
    assert record.logical_locator == "abc123def456"


# ── Provenance ───────────────────────────────────────────────────


def test_authority_is_measured_and_evidence_class_is_m():
    record = si.build_story_record(_story_result())
    assert record.authority is Authority.MEASURED
    assert record.evidence_class == "[M]"


def test_structured_ledger_fields_carried_through():
    record = si.build_story_record(_story_result(perturbation_strength=0.5, test_executed_success=False))
    assert record.perturbation_strength == 0.5
    assert record.test_executed_success is False
    # Story-level confidence is not a thing — it's a per-attempt signal (ledger_ingestion).
    assert record.confidence is None


def test_causes_is_none_for_a_story_record():
    # `causes` is only ever set on source_type == "actuation" records.
    record = si.build_story_record(_story_result())
    assert record.causes is None


# ── Text rendering ────────────────────────────────────────────────


def test_text_mentions_model_and_condition():
    record = si.build_story_record(_story_result())
    assert "deepseek/deepseek-v4-flash" in record.text
    assert "clean" in record.text


# ── No-op relabel (docs/data_integrity_findings.md treatment rule 1) ──


def test_noop_early_degrade_relabeled_to_clean_with_caveat():
    # A non-instrumented (test_executed_success=None) early_degrade cell is a no-op:
    # relabeled to "clean" with a caveat that the original label was a no-op.
    record = si.build_story_record(
        _story_result(perturbation_condition="early_degrade", test_executed_success=None)
    )
    assert "[deepseek/deepseek-v4-flash, clean]" in record.text
    assert "no-op" in record.text  # the caveat is present


def test_instrumented_early_degrade_keeps_its_label():
    # An instrumented early_degrade cell (test_executed_success is a real bool) genuinely
    # perturbed — it keeps "early_degrade" and carries no caveat.
    record = si.build_story_record(
        _story_result(perturbation_condition="early_degrade", test_executed_success=True)
    )
    assert "[deepseek/deepseek-v4-flash, early_degrade]" in record.text
    assert "no-op" not in record.text


def test_noop_bad_seed_relabeled_to_clean():
    record = si.build_story_record(
        _story_result(perturbation_condition="bad_seed", test_executed_success=None)
    )
    assert "[deepseek/deepseek-v4-flash, clean]" in record.text
    assert "no-op" in record.text


def test_genuinely_clean_cell_is_untouched():
    record = si.build_story_record(
        _story_result(perturbation_condition="clean", test_executed_success=None)
    )
    assert "[deepseek/deepseek-v4-flash, clean]" in record.text
    assert "no-op" not in record.text


# ── Reused artifact/event contract ──────────────────────────────


def test_content_hash_equals_sha256_of_record_to_artifact():
    record = si.build_story_record(_story_result())
    import hashlib

    assert record.content_hash == hashlib.sha256(record_to_artifact(record)).hexdigest()


# ── Determinism / idempotence ───────────────────────────────────


def test_repeated_derivation_is_idempotent():
    a = si.build_story_record(_story_result())
    b = si.build_story_record(_story_result())
    assert a.knowledge_id == b.knowledge_id
    assert a.entity_id == b.entity_id
    assert a.content_hash == b.content_hash


def test_changed_body_yields_a_different_knowledge_id():
    a = si.build_story_record(_story_result())
    b = si.build_story_record(_story_result(test_executed_success=False))
    assert a.knowledge_id != b.knowledge_id
    # entity_id (the logical identity) is unaffected by a content change.
    assert a.entity_id == b.entity_id


def test_source_revision_is_the_last_committed_session():
    record = si.build_story_record(_story_result())
    assert record.commit_sha == "commit_s2"


def test_source_revision_falls_back_when_no_session_committed():
    sr = _story_result(sessions=[{"session_number": 1, "commit_hash": "", "agentic": {}}])
    record = si.build_story_record(sr)
    assert record.commit_sha == si.REVISION_FALLBACK


# ── Errors / batch pre-filter ────────────────────────────────────


def test_build_story_record_raises_without_story_id():
    import pytest

    with pytest.raises(ValueError):
        si.build_story_record(_story_result(story_id=""))


def test_derive_story_records_skips_missing_story_id_instead_of_raising():
    assert si.derive_story_records(_story_result(story_id="")) == []


def test_derive_story_records_returns_one_record():
    records = si.derive_story_records(_story_result())
    assert len(records) == 1
    assert records[0].source_type == "story"


# ── derive_story_records_from_run_output (plan step 11's run.py adapter) ─


def _run_output(**overrides) -> dict:
    base = {
        "experiment": "task_manager_api",
        "model": "DeepSeek v4 Flash",
        "runs": [
            {"operator": "baseline", "correctness": 0.9, "cost_usd": 0.5, "total_tokens": 1000},
            {"operator": "inject_alien_vocab", "correctness": 0.7, "cost_usd": 0.3, "total_tokens": 800},
        ],
    }
    base.update(overrides)
    return base


def test_run_output_adapter_reuses_the_save_results_filename_formula_as_story_id():
    # scripts/run.py's _save_results writes to results_dir / f"{name}_{model_slug}.json"
    # — this adapter must derive the SAME string as its synthetic story_id, not a second
    # identity formula.
    records = si.derive_story_records_from_run_output(_run_output())
    assert len(records) == 1
    assert records[0].logical_locator == "task_manager_api_deepseek_v4_flash"
    assert records[0].source_uri == "story:task_manager_api_deepseek_v4_flash"


def test_run_output_adapter_produces_a_valid_story_record():
    records = si.derive_story_records_from_run_output(_run_output())
    assert records[0].source_type == "story"
    assert records[0].authority is Authority.MEASURED
    assert records[0].evidence_class == "[M]"


def test_run_output_adapter_raises_without_experiment_key():
    import pytest

    with pytest.raises(ValueError):
        si.derive_story_records_from_run_output(_run_output(experiment=""))


def test_run_output_adapter_is_idempotent():
    a = si.derive_story_records_from_run_output(_run_output())
    b = si.derive_story_records_from_run_output(_run_output())
    assert a[0].knowledge_id == b[0].knowledge_id


def test_run_output_adapter_changed_runs_yields_a_different_knowledge_id():
    a = si.derive_story_records_from_run_output(_run_output())
    b = si.derive_story_records_from_run_output(_run_output(runs=[]))
    assert a[0].knowledge_id != b[0].knowledge_id
    # Same experiment+model -> same logical entity, still.
    assert a[0].entity_id == b[0].entity_id
