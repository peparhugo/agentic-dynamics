"""Tests for the prompt-constructor: schema validation, constraint/citation/tool checks,
one-repair, deterministic fallback, and no-fork keying."""

import json
from dataclasses import fields

from instrument.prompt_constructor import (
    DEFAULT_CONSTRUCTOR_MODEL,
    SCHEMA_VERSION,
    STABLE_INSTRUCTION_PREFIX,
    AugmentedPrompt,
    ConstructionRequest,
    EvidenceUnit,
    ModelPromptConstructor,
    build_constructor_prompt,
    build_deterministic_plan,
    construction_cache_key,
    hash_work_item,
    parse_model_json,
    plan_from_dict,
    render_prompt,
    validate_plan,
)


def _evidence(knowledge_id: str, text: str = "evidence text", authority: str = "source") -> EvidenceUnit:
    return EvidenceUnit(
        knowledge_id=knowledge_id,
        text=text,
        authority=authority,
        citation=f"[K:{knowledge_id}@abc:loc]",
        content_hash=f"ch:{knowledge_id}",
        token_count=len(text.split()),
    )


def _request(**overrides) -> ConstructionRequest:
    kwargs = dict(
        raw_work_item="implement the widget",
        phase_objective="build a widget",
        pinned_policy="AGENTS.md: never consume confidence unmeasured",
        evidence=[_evidence("k1"), _evidence("k2", authority="advisory")],
        inherited_tools=["edit", "bash", "grep"],
        user_constraints=["no comments", "run tests"],
        executor_model="deepseek/deepseek-v4-pro",
        commit_sha="abc1234",
    )
    kwargs.update(overrides)
    return ConstructionRequest(**kwargs)


def _valid_plan_dict(raw: str = "implement the widget") -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "task_intent": "implement the widget",
        "raw_work_item_hash": hash_work_item(raw),
        "hard_constraints": [{"text": "no comments", "source": "user", "citation": "user:1"}],
        "relevant_targets": [],
        "evidence_claims": [
            {"claim": "the widget needs a cache", "evidence_ids": ["k1"], "authority": "source"}
        ],
        "conflicts_and_unknowns": [],
        "acceptance_checks": [{"check": "tests pass", "source": "policy"}],
        "allowed_tools": ["edit", "grep"],
        "executor_instructions": "implement and test",
    }


# ── Schema validation ───────────────────────────────────────────

def test_valid_plan_passes():
    request = _request()
    plan = plan_from_dict(_valid_plan_dict())
    assert validate_plan(plan, request, request.evidence) == []


def test_schema_version_rejected():
    request = _request()
    d = _valid_plan_dict()
    d["schema_version"] = "prompt-plan/v0"
    assert validate_plan(plan_from_dict(d), request, request.evidence)


def test_raw_work_item_hash_mismatch_rejected():
    request = _request()
    d = _valid_plan_dict()
    d["raw_work_item_hash"] = hash_work_item("a different request")
    errors = validate_plan(plan_from_dict(d), request, request.evidence)
    assert any("raw_work_item_hash" in e for e in errors)


def test_empty_task_intent_rejected():
    request = _request()
    d = _valid_plan_dict()
    d["task_intent"] = ""
    assert validate_plan(plan_from_dict(d), request, request.evidence)


def test_hash_work_item_is_sha256():
    assert hash_work_item("x") == "sha256:" + __import__("hashlib").sha256(b"x").hexdigest()


# ── Invented-constraint rejection ───────────────────────────────

def test_invented_constraint_rejected():
    request = _request()
    d = _valid_plan_dict()
    d["hard_constraints"] = [
        {"text": "the model must use Rust", "source": "policy", "citation": "policy:AGENTS.md"}
    ]
    errors = validate_plan(plan_from_dict(d), request, request.evidence)
    assert any("invented constraint" in e for e in errors)


def test_evidence_sourced_constraint_rejected():
    # Retrieved evidence must stay evidence, never become control text.
    request = _request()
    d = _valid_plan_dict()
    d["hard_constraints"] = [
        {"text": "no comments", "source": "evidence", "citation": "[K:k1]"}
    ]
    errors = validate_plan(plan_from_dict(d), request, request.evidence)
    assert any("control" in e or "authority escalation" in e for e in errors)


# ── Citation validity ───────────────────────────────────────────

def test_claim_citing_unknown_knowledge_id_rejected():
    request = _request()
    d = _valid_plan_dict()
    d["evidence_claims"] = [{"claim": "x", "evidence_ids": ["k_missing"], "authority": "source"}]
    errors = validate_plan(plan_from_dict(d), request, request.evidence)
    assert any("unknown knowledge_id" in e for e in errors)


def test_target_citing_unknown_knowledge_id_rejected():
    request = _request()
    d = _valid_plan_dict()
    d["relevant_targets"] = [{"path": "src/a.py", "symbols": [], "evidence_ids": ["k_missing"]}]
    errors = validate_plan(plan_from_dict(d), request, request.evidence)
    assert any("unknown knowledge_id" in e for e in errors)


def test_claim_authority_must_match_cited_evidence():
    request = _request()
    d = _valid_plan_dict()
    # k1's evidence authority is "source", not "policy".
    d["evidence_claims"] = [{"claim": "x", "evidence_ids": ["k1"], "authority": "policy"}]
    errors = validate_plan(plan_from_dict(d), request, request.evidence)
    assert any("authority" in e for e in errors)


# ── Tool-subset enforcement ─────────────────────────────────────

def test_tool_privilege_expansion_rejected():
    request = _request()
    d = _valid_plan_dict()
    d["allowed_tools"] = ["edit", "grep", "sudo"]
    errors = validate_plan(plan_from_dict(d), request, request.evidence)
    assert any("privileges" in e for e in errors)


def test_tool_subset_accepted():
    request = _request()
    d = _valid_plan_dict()
    d["allowed_tools"] = ["edit"]
    assert validate_plan(plan_from_dict(d), request, request.evidence) == []


# ── One-repair flow ─────────────────────────────────────────────

def _runner(responses: list[str]):
    call_count = {"n": 0}

    def run(_prompt: str) -> str:
        i = min(call_count["n"], len(responses) - 1)
        call_count["n"] += 1
        return responses[i]

    return run, call_count


def test_construct_repairs_once_then_succeeds():
    good = json.dumps(_valid_plan_dict())
    bad = "{ not valid json"
    run, calls = _runner([bad, good])
    constructor = ModelPromptConstructor(run_constructor=run)
    result = constructor.construct(_request())
    assert isinstance(result, AugmentedPrompt)
    assert result.repair_count == 1
    assert result.fallback is False
    assert calls["n"] == 2  # initial + exactly one repair


def test_construct_repair_at_most_once():
    bad = "{ still not json"
    run, calls = _runner([bad, bad])
    constructor = ModelPromptConstructor(run_constructor=run)
    result = constructor.construct(_request())
    assert result.fallback is True
    assert result.repair_count == 1
    assert calls["n"] == 2  # never a third call


def test_construct_no_repair_when_valid():
    good = json.dumps(_valid_plan_dict())
    run, calls = _runner([good])
    constructor = ModelPromptConstructor(run_constructor=run)
    result = constructor.construct(_request())
    assert result.repair_count == 0
    assert result.fallback is False
    assert calls["n"] == 1


# ── Deterministic fallback ──────────────────────────────────────

def test_deterministic_fallback_has_no_model_claims():
    request = _request()
    plan = build_deterministic_plan(request, request.evidence)
    assert plan.evidence_claims == []
    assert plan.executor_instructions == ""
    assert plan.schema_version == SCHEMA_VERSION
    assert plan.raw_work_item_hash == hash_work_item(request.raw_work_item)


def test_fallback_render_contains_verbatim_item_policy_and_evidence():
    request = _request()
    plan = build_deterministic_plan(request, request.evidence)
    rendered = render_prompt(plan, request, request.evidence)
    assert request.raw_work_item in rendered          # verbatim, never replaced
    assert request.pinned_policy in rendered          # pinned policy present
    assert request.evidence[0].text in rendered       # evidence text present
    assert "Implement and test".lower() not in rendered.lower()  # no model guidance


def test_construct_falls_back_to_deterministic_render():
    bad = "{}"  # valid JSON but fails schema
    run, _ = _runner([bad, bad])
    constructor = ModelPromptConstructor(run_constructor=run)
    result = constructor.construct(_request())
    assert result.fallback is True
    assert result.prompt_plan.evidence_claims == []
    assert result.raw_work_item_hash == hash_work_item("implement the widget")


def test_render_order_is_deterministic():
    request = _request()
    plan = plan_from_dict(_valid_plan_dict())
    r1 = render_prompt(plan, request, request.evidence)
    r2 = render_prompt(plan, request, request.evidence)
    assert r1 == r2
    # Objective precedes the verbatim work item, which precedes pinned policy.
    assert r1.index("## Objective") < r1.index("## Work item (verbatim)")
    assert r1.index("## Work item (verbatim)") < r1.index("## Pinned policy")


# ── No-fork keying ──────────────────────────────────────────────

def test_construction_request_has_no_session_field():
    names = {f.name for f in fields(ConstructionRequest)}
    assert "session_id" not in names
    assert "fork_id" not in names


def test_cache_key_stable_for_identical_semantic_inputs():
    a = _request()
    b = _request()
    assert construction_cache_key(a) == construction_cache_key(b)


def test_cache_key_changes_with_evidence():
    a = _request()
    b = _request(evidence=[_evidence("k1"), _evidence("k2", authority="advisory"), _evidence("k3")])
    assert construction_cache_key(a) != construction_cache_key(b)


def test_cache_key_changes_with_raw_work_item():
    a = _request()
    b = _request(raw_work_item="a completely different task")
    assert construction_cache_key(a) != construction_cache_key(b)


def test_stable_prefix_is_constant_across_requests():
    # The provider-cacheable prefix is identical for different work items; only the
    # new-input tail differs. No session is forked.
    a = _request(raw_work_item="task one")
    b = _request(raw_work_item="task two")
    pa = build_constructor_prompt(a, a.evidence)
    pb = build_constructor_prompt(b, b.evidence)
    assert pa.startswith(STABLE_INSTRUCTION_PREFIX)
    assert pb.startswith(STABLE_INSTRUCTION_PREFIX)
    assert pa.split(STABLE_INSTRUCTION_PREFIX)[1] != pb.split(STABLE_INSTRUCTION_PREFIX)[1]


def test_default_model_is_cheapest_flash():
    assert DEFAULT_CONSTRUCTOR_MODEL == "deepseek/deepseek-v4-flash"


def test_parse_model_json_tolerates_fences():
    assert parse_model_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_model_json("not json") is None
