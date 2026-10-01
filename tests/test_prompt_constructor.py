"""Tests for the prompt-constructor: schema validation, constraint/citation/tool checks,
one-repair, deterministic fallback, and no-fork keying."""

import ast
import json
import sys
import types
from dataclasses import fields
from pathlib import Path

import pytest

from agentic_dynamics.knowledge.augment import augment_prompt
from agentic_dynamics.knowledge.context_layers import (
    LAYER_SELF,
    LAYER_STATUS_EXCLUDED,
    LAYER_STATUS_NAMED_ABSENT,
    LAYER_STATUS_SERVED,
    PROJECT_KNOWLEDGE_SCOPE,
    ROLE_IMPLEMENTATION,
    ROLE_PLANNING,
    ROLE_REVIEW,
    ROLE_UNKNOWN,
    RUN_FINDINGS_SCOPE_TOKEN,
    SERVING_SCOPE_GRANTS_KEY,
    SERVING_SCOPE_POLICY,
    UNRESOLVED_WITHHELD_REASON,
    LayerRoute,
    phase_serving_scopes,
    resolve_layer_route,
    resolve_phase_layers,
    serving_scope_grants,
)
from agentic_dynamics.knowledge.prompt_constructor import (
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
from agentic_dynamics.knowledge.retrieval import SOURCE_TYPE_RESOLVER_ERROR_KEY


def _evidence(
    knowledge_id: str, text: str = "evidence text", authority: str = "source"
) -> EvidenceUnit:
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
    d["hard_constraints"] = [{"text": "no comments", "source": "evidence", "citation": "[K:k1]"}]
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
    assert request.raw_work_item in rendered  # verbatim, never replaced
    assert request.pinned_policy in rendered  # pinned policy present
    assert request.evidence[0].text in rendered  # evidence text present
    assert "Implement and test".lower() not in rendered.lower()  # no model guidance


def test_construct_falls_back_to_deterministic_render():
    bad = "{}"  # valid JSON but fails schema
    run, _ = _runner([bad, bad])
    constructor = ModelPromptConstructor(run_constructor=run)
    result = constructor.construct(_request())
    assert result.fallback is True
    assert result.prompt_plan.evidence_claims == []
    assert result.raw_work_item_hash == hash_work_item("implement the widget")


def test_constructor_call_failure_has_named_safe_fallback():
    request = _request()

    def fail(_prompt: str) -> str:
        raise RuntimeError("constructor unavailable")

    result = ModelPromptConstructor(run_constructor=fail).construct(request)

    assert result.fallback is True
    assert result.fallback_reason == "constructor_call_failed"
    assert request.raw_work_item in result.prompt
    assert request.pinned_policy in result.prompt
    assert result.prompt.strip()


def test_augmentation_failure_preserves_base_prompt_and_names_stage():
    base_prompt = "the already valid executor prompt"
    constructor_called = False

    def fail_retrieve(**_kwargs):
        raise RuntimeError("retrieval unavailable")

    def should_not_construct(_request):
        nonlocal constructor_called
        constructor_called = True
        raise AssertionError("a retrieval failure must not invoke construction")

    outcome = augment_prompt(
        base_prompt=base_prompt,
        goal="test the fallback",
        phase_def={},
        model="test/model",
        commit_sha="abc",
        inherited_tools=["read"],
        pinned_policy="policy",
        rag_params={},
        retrieve_fn=fail_retrieve,
        construct_fn=should_not_construct,
    )

    assert outcome.prompt == base_prompt
    assert outcome.fallback is True
    assert outcome.fallback_mode == "no_rag"
    assert outcome.fallback_reason == "retrieve_failed"
    assert "RuntimeError: retrieval unavailable" in outcome.error
    assert constructor_called is False


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
    # The pin names the LIVE volume model (the L39 sweep direction), whose id a fresh
    # provider process accepts, and it is NOT the retired id a fresh process refuses.
    assert DEFAULT_CONSTRUCTOR_MODEL == "deepseek/deepseek-flash"
    assert DEFAULT_CONSTRUCTOR_MODEL != "deepseek/deepseek-v4-flash"


def test_default_model_pin_assertion_is_mutation_sensitive(monkeypatch):
    """u3: the live-pin guard is NON-VACUOUS — rebinding the binding it reads FAILS it.

    A guard is only meaningful if it can fail. The credited pin test reads the global
    THIS module imported; the reviewer verified the mutation by hand, so this test makes
    the suite prove it (the exact mutation the reviewer's note describes: rebind the
    TEST's imported constant to the retired id). With the real binding the credited pin
    assertion passes (positive control); after ``monkeypatch`` rebinds that binding to the
    retired id it MUST raise, so a future edit that turned the pin into a tautology (or
    read a stale/different binding) passes the credited assertion but FAILS here — the
    guard cannot silently decay into a snapshot of a green module. Mirrors the sweep's
    ``test_retired_id_sweep_detects_a_reintroduced_live_literal`` non-vacuity self-test.
    """
    module = sys.modules[__name__]
    # Positive control: the binding is real and the credited assertion passes on it.
    test_default_model_is_cheapest_flash()
    # The mutation the assertion actually reads: THIS module's imported global.
    monkeypatch.setattr(module, "DEFAULT_CONSTRUCTOR_MODEL", _RETIRED_MODEL_ID)
    assert module.DEFAULT_CONSTRUCTOR_MODEL != "deepseek/deepseek-flash"
    # The credited pin assertion now FAILS — mutation-sensitive, not vacuous.
    with pytest.raises(AssertionError):
        test_default_model_is_cheapest_flash()


def test_source_pin_repointed_to_retired_is_refused_by_default_resolution(monkeypatch):
    """u3: a SOURCE re-point of the pin to the retired id is refused by NAME at resolution.

    The credited pin test reads the test module's imported binding, so an in-memory
    mutation of ONLY ``prompt_constructor.DEFAULT_CONSTRUCTOR_MODEL`` (the reviewer's
    first, weaker mutation) does not trip it. This guard closes that hole at the consumer:
    ``resolve_constructor_model(None)`` re-reads the SOURCE constant at call time, so a
    source re-point to the retired family raises ``RetiredConstructorModelError`` — the
    DEFAULT path can never silently carry the retired id, whichever binding a caller holds.
    """
    import agentic_dynamics.knowledge.augment as augment
    import agentic_dynamics.knowledge.prompt_constructor as prompt_constructor

    # Positive control: the live source pin resolves cleanly through the default path.
    assert augment.resolve_constructor_model(None) == DEFAULT_CONSTRUCTOR_MODEL
    # The reviewer's weaker mutation: re-point only the SOURCE module binding.
    monkeypatch.setattr(prompt_constructor, "DEFAULT_CONSTRUCTOR_MODEL", _RETIRED_MODEL_ID)
    with pytest.raises(augment.RetiredConstructorModelError) as exc:
        augment.resolve_constructor_model(None)
    assert _RETIRED_MODEL_ID in str(exc.value)


def test_construction_defaults_carry_the_live_pin_not_the_retired_id():
    """u5: the LIVE pin is the DEFAULT on both construction paths, not only the constant.

    A mutation-sensitive discriminator beyond the module-constant assertion: the dataclass
    default that the seam builds its ``ConstructionRequest`` with, and the model-backed
    constructor's own default model, must BOTH be the live volume id and differ from the
    retired id. Rebinding ``DEFAULT_CONSTRUCTOR_MODEL`` to the retired
    ``deepseek/deepseek-v4-flash`` — the exact change that would make every augmented phase
    call a fresh provider process with a REFUSED id — fails every assertion here, so the pin
    cannot be silently re-pointed while leaving either default behind.
    """
    assert DEFAULT_CONSTRUCTOR_MODEL == "deepseek/deepseek-flash"
    assert DEFAULT_CONSTRUCTOR_MODEL != "deepseek/deepseek-v4-flash"
    # The request the seam builds (no explicit override) carries the live pin...
    assert _request().constructor_model == DEFAULT_CONSTRUCTOR_MODEL
    # ...and the model-backed constructor's default argument is the same live pin.
    assert ModelPromptConstructor().model == DEFAULT_CONSTRUCTOR_MODEL


def test_default_construct_fn_resolves_live_model_id():
    """The CONSUMER path — not just the constant — resolves the LIVE volume id.

    ``augment.default_construct_fn`` is what an augmented phase actually wires in
    (``workflow_runner`` calls it when ``rag_augment`` is enabled without an explicit
    injection). A sweep of the touched modules (``prompt_constructor``, ``augment``,
    ``retrieval``, ``embeddings``, ``context_layers``, ``workflow_runner``) found the
    retired id only in the historical comment on ``DEFAULT_CONSTRUCTOR_MODEL``; every
    selection flows through that pinned constant. This test guards that consumer end to
    end: the built constructor carries the live id AND hands it to the injected executor.
    """
    import agentic_dynamics.knowledge.augment as augment

    seen: list[str] = []

    def run_agent(prompt, *, model, **kwargs):
        seen.append(model)
        return types.SimpleNamespace(final_response="{}")

    built = augment.default_construct_fn({}, run_agent)
    # The default (no rag_params override) resolves the pinned LIVE constant...
    assert built.__self__.model == DEFAULT_CONSTRUCTOR_MODEL
    assert built.__self__.model == "deepseek/deepseek-flash"
    assert built.__self__.model != "deepseek/deepseek-v4-flash"

    # ...and the real consumer path hands that id to the injected executor.
    built(_request())
    assert seen, "the constructor never called the injected run_agent"
    assert all(model == "deepseek/deepseek-flash" for model in seen)
    assert "deepseek/deepseek-v4-flash" not in seen

    # An explicit override is still honored: the id stays a tunable prior.
    overridden = augment.default_construct_fn(
        {"constructor_model": "openai/gpt-6-astra"}, run_agent
    )
    assert overridden.__self__.model == "openai/gpt-6-astra"


def test_resolve_constructor_model_refuses_retired_family_by_name():
    """u5: the override guard refuses the RETIRED family by name, defaults to the live id.

    The guard is FAMILY-keyed, not one literal: any provider namespace carrying the retired
    family is refused, so a re-providered retired id cannot slip through. A valid override
    and the no-override default pass unchanged.
    """
    import agentic_dynamics.knowledge.augment as augment

    # No override (and an explicit empty) resolves to the pinned live volume id.
    assert augment.resolve_constructor_model(None) == DEFAULT_CONSTRUCTOR_MODEL
    assert augment.resolve_constructor_model("") == DEFAULT_CONSTRUCTOR_MODEL
    # A live, non-retired override is honored (the id stays a tunable prior).
    assert augment.resolve_constructor_model("openai/gpt-6-astra") == "openai/gpt-6-astra"
    # The retired family is refused by name — for THIS provider and ANY other namespace.
    for retired in ("deepseek/deepseek-v4-flash", "otherprovider/deepseek-v4-flash"):
        with pytest.raises(augment.RetiredConstructorModelError) as exc:
            augment.resolve_constructor_model(retired)
        message = str(exc.value)
        assert "retired" in message.lower()
        assert retired in message
        assert DEFAULT_CONSTRUCTOR_MODEL in message


def test_default_construct_fn_refuses_retired_override_before_any_executor_call():
    """u5: an explicit RETIRED ``constructor_model`` override fails LOUDLY at wiring time.

    Falsifier for the pre-u5 behavior: if the retired override were accepted, no error is
    raised and the injected executor is handed the retired id — so this test fails on
    reversion. The refusal precedes any executor call (``calls == []``).
    """
    import agentic_dynamics.knowledge.augment as augment

    calls: list[str] = []

    def run_agent(prompt, *, model, **kwargs):
        calls.append(model)
        return types.SimpleNamespace(final_response="{}")

    with pytest.raises(augment.RetiredConstructorModelError) as exc:
        augment.default_construct_fn({"constructor_model": "deepseek/deepseek-v4-flash"}, run_agent)
    assert calls == []  # refused BEFORE any executor call
    assert "deepseek/deepseek-v4-flash" in str(exc.value)
    assert DEFAULT_CONSTRUCTOR_MODEL in str(exc.value)


def test_augment_prompt_names_retired_override_never_silently_constructs():
    """u5: the seam records a NAMED cause for a retired override instead of constructing.

    The guarded construct step resolves the retired id and raises; the deterministic fallback
    preserves the base prompt and names the typed cause, so a retired override is never
    silently accepted (and the injected constructor is never invoked).
    """
    called = {"n": 0}

    def retrieve_fn(**_kwargs):
        return _FakeAttempt([])

    def construct_fn(_request):
        called["n"] += 1
        return _FakeConstructed([])

    outcome = augment_prompt(
        base_prompt="base",
        goal="build",
        phase_def={"name": "execute", "kind": "agent"},
        model="deepseek/deepseek-flash",
        commit_sha="abc",
        inherited_tools=["read"],
        pinned_policy="policy",
        rag_params={"constructor_model": "deepseek/deepseek-v4-flash"},
        retrieve_fn=retrieve_fn,
        construct_fn=construct_fn,
    )

    assert outcome.prompt == "base"
    assert outcome.fallback is True
    assert outcome.fallback_reason == "construct_failed"
    assert "RetiredConstructorModelError" in outcome.error
    assert called["n"] == 0


#: The modules this retrieval-serving unit owns for the retired-id sweep. The sweep is
#: deliberately BOUNDED to them: they are the modules the repair touched. The retired id
#: legitimately appears here only as non-executable prose (the history comment on
#: ``DEFAULT_CONSTRUCTOR_MODEL`` and the docstring on ``augment.default_construct_fn``).
_TOUCHED_MODULE_RELATIVE_PATHS = (
    "src/agentic_dynamics/knowledge/prompt_constructor.py",
    "src/agentic_dynamics/knowledge/augment.py",
    "src/agentic_dynamics/knowledge/retrieval.py",
    "src/agentic_dynamics/knowledge/embeddings.py",
    "src/agentic_dynamics/knowledge/context_layers.py",
    "src/agentic_dynamics/runtime/workflow_runner.py",
)

#: The retired constructor/task model id — refused by a fresh provider process (register L39).
_RETIRED_MODEL_ID = "deepseek/deepseek-v4-flash"

#: NAMED CONTROLLER FOLLOW-UP — retired-id pins OUTSIDE this unit's declared write scope are
#: NOT silently claimed swept. They remain live selection literals and need a separate decision:
#:   runtime/posthoc.py:45            DEFAULT_REVIEW_MODEL
#:   runtime/story/conditions.py:37   compiler_model default
#:   control/model_policy.py:33       FLASH_MODEL (+ the retired-id mention at :19)
#:   reporting/review.py:311,397,694  review-model defaults
#:   reporting/opencode_analyzer.py:176  analyzer-model default
#: They are recorded here so the bounded sweep above cannot be mistaken for a repo-wide clean bill.


def _docstring_line_numbers(tree: ast.AST) -> set[int]:
    """Line numbers covered by module/class/function docstrings (non-executable prose)."""
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                doc = body[0].value
                lines.update(range(doc.lineno, (doc.end_lineno or doc.lineno) + 1))
    return lines


def _retired_id_offenders(source: str, rel: str) -> list[str]:
    """Live retired-id selection literals in ONE module's source text (pure).

    A source line naming the retired id is permitted prose ONLY when it is a ``#`` comment
    or falls inside a module/class/function docstring; any AST string constant outside a
    docstring that contains the id is a live selection literal. Extracted from the sweep
    test as a pure function so the detector itself is unit-testable against synthetic
    sources — a refactor that silently made the sweep vacuous (e.g. an early ``return []``)
    would pass a clean-tree assertion but fail the non-vacuity guard below.
    """
    tree = ast.parse(source, filename=rel)
    doc_lines = _docstring_line_numbers(tree)
    offenders: list[str] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        if _RETIRED_MODEL_ID not in line:
            continue
        if line.lstrip().startswith("#") or lineno in doc_lines:
            continue
        offenders.append(f"{rel}:{lineno}: {line.strip()}")
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _RETIRED_MODEL_ID in node.value
            and node.lineno not in doc_lines
        ):
            offenders.append(f"{rel}:{node.lineno}: executable string literal {node.value!r}")
    return offenders


def test_retired_id_sweep_detects_a_reintroduced_live_literal():
    """u7: the sweep DETECTOR is non-vacuous — a re-introduced live literal is caught.

    ``test_retired_constructor_id_never_a_live_selection_literal`` asserts the six touched
    modules are clean, but a clean result is only meaningful if the detector can actually
    flag a violation. This self-test drives synthetic sources through the SAME pure
    ``_retired_id_offenders`` helper: an assignment or call-argument naming the retired id
    is an offender, while a ``#`` comment or a docstring naming it is permitted prose. A
    regression that neutered the detection (e.g. returning ``[]`` unconditionally) passes
    the clean-modules assertion but FAILS here, so the sweep cannot silently decay into a
    snapshot of a green file instead of a mutation-sensitive gate.
    """
    # A live assignment / call-argument on the retired id is flagged...
    assert _retired_id_offenders(
        'DEFAULT_CONSTRUCTOR_MODEL = "deepseek/deepseek-v4-flash"\n', "synthetic.py"
    )
    assert _retired_id_offenders('chosen = select("deepseek/deepseek-v4-flash")\n', "synthetic.py")
    # ...while the same id as a comment or as a docstring is permitted prose.
    assert _retired_id_offenders("# retired: deepseek/deepseek-v4-flash\n", "synthetic.py") == []
    assert (
        _retired_id_offenders('"""retired: deepseek/deepseek-v4-flash"""\n', "synthetic.py") == []
    )


def test_retired_constructor_id_never_a_live_selection_literal():
    """Sweep the touched modules: the retired id survives only as non-executable prose.

    The credited repair re-pointed ``DEFAULT_CONSTRUCTOR_MODEL`` to the live volume id
    (``deepseek/deepseek-flash``). This guard proves the retired id cannot silently
    reappear as a LIVE selection literal in any touched module: every source line naming
    it must be a ``#`` comment or a module/class/function docstring, and no AST string
    constant outside a docstring may contain it. A new assignment/argument on the retired
    id fails this gate — the sweep is mutation-sensitive, not a snapshot. The detection
    itself is proven non-vacuous by ``test_retired_id_sweep_detects_a_reintroduced_live_literal``.

    Sibling pins OUTSIDE the touched modules are a named controller follow-up (see the
    ``_RETIRED_MODEL_ID`` note above), never claimed swept here.
    """
    repo_root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    for rel in _TOUCHED_MODULE_RELATIVE_PATHS:
        path = repo_root / rel
        offenders.extend(_retired_id_offenders(path.read_text(encoding="utf-8"), rel))
    assert not offenders, (
        "retired constructor id appears as a live selection literal:\n" + "\n".join(offenders)
    )


def test_parse_model_json_tolerates_fences():
    assert parse_model_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_model_json("not json") is None


# ── u4: layer-route → retrieval shaping + per-phase context_route ──
#
# The gate for the u4 slice (F4 repair): `augment_prompt` with a REAL route emits
# `AugmentationOutcome.context_route` with one honest disposition per resolved layer; a
# layer whose leg failed is `named_absent`, never an empty `served`; every served item
# carries a layer; prohibited self-layer (L4) content is excluded; an UNKNOWN/unroutable
# request records its served items as unclassified and serves nothing. These tests use
# only local test doubles — no store, no network, no optional deps.


class _FakeCandidate:
    """A `Candidate`-shaped double carrying exactly the fields the seam reads."""

    def __init__(self, cid: str, source_type: str = "code") -> None:
        self.id = cid
        self.text = f"text for {cid}"
        self.authority = "source"
        self.commit_sha = "abc"
        self.source_type = source_type
        self.locator = f"loc:{cid}"
        self.content_hash = ""
        self.token_count = 1
        self.pattern_payload = None

    def citation(self) -> str:
        return f"[K:{self.id}@abc:{self.locator}]"


class _FakeAttempt:
    """A `RetrievalAttempt`-shaped double."""

    def __init__(
        self,
        selected: list[_FakeCandidate],
        *,
        leg_errors: dict[str, str] | None = None,
        fallback_mode: str = "full",
    ) -> None:
        self.selected_evidence = selected
        self.leg_errors = leg_errors or {}
        self.fallback_mode = fallback_mode
        self.retrieval_attempt_id = "ret-1"


class _FakeConstructed:
    """An `AugmentedPrompt`-shaped double naming the evidence the worker received."""

    def __init__(self, evidence_ids: list[str], *, fallback: bool = False) -> None:
        self.prompt = "AUGMENTED PROMPT"
        self.fallback = fallback
        self.fallback_reason = "" if not fallback else "constructor_fallback"
        self.evidence_ids = evidence_ids
        self.constructor_attempt_id = "con-1"
        self.versions: dict[str, str] = {}
        self.token_counts: dict[str, int] = {}
        self.cost_usd = 0.0


def test_resolve_layer_route_maps_layers_to_retrieval_shaping():
    """The shaping carries the route's source types, shared ids, and L3 pattern projection."""
    planning = resolve_phase_layers("prior", "agent")  # L1 + L2 + L3
    shape = resolve_layer_route(planning, goal="what happened before?", base_prompt="plan it")
    assert shape.source_types == planning.source_types
    assert "code" in shape.source_types  # L1 structure material
    assert "story" in shape.source_types  # L2 history material
    assert "pattern" in shape.source_types  # L3 outcomes material
    assert shape.pattern_projection is True  # L3 resolved -> pattern records stay eligible
    assert shape.shared_repository_ids == ()
    assert shape.intent == "outcomes"

    implementation = resolve_phase_layers("execute", "agent")  # L1 + L2, no L3
    shape_i = resolve_layer_route(implementation, goal="build it", base_prompt="code")
    assert shape_i.pattern_projection is False
    assert "code" in shape_i.source_types

    # An absent/unknown route is the identity shape — the pre-existing retrieval path.
    unknown = resolve_layer_route(None)
    assert unknown.source_types == ()
    assert unknown.shared_repository_ids == ()
    assert unknown.pattern_projection is False
    assert unknown.intent == "unknown"


# ── u5: serving-scope policy (explicit, default-empty, bounded) ──
#
# The gate for the u5 slice: `serving_scope_grants(role)` is DEFAULT-EMPTY (no shared
# visibility is ever granted implicitly), an EXPLICIT policy call returns only the bounded
# grants and never a wildcard, and the promoted no-hint route is unchanged
# (`resolve_phase_layers("prior", "agent").shared_scopes == ()`). No store, no network.


def test_serving_scope_grants_is_default_empty():
    """No explicit policy -> no grant; unknown/unlisted roles -> empty (never global)."""
    # DEFAULT-EMPTY: the no-policy call grants nothing, so routing alone never widens.
    assert serving_scope_grants(ROLE_PLANNING) == ()
    assert serving_scope_grants(ROLE_IMPLEMENTATION) == ()
    assert serving_scope_grants(ROLE_UNKNOWN) == ()
    # A role absent from the explicit table, an empty role, and a non-mapping policy are empty.
    assert serving_scope_grants("not-a-role", policy=SERVING_SCOPE_POLICY) == ()
    assert serving_scope_grants("", policy=SERVING_SCOPE_POLICY) == ()
    assert serving_scope_grants(ROLE_PLANNING, policy="nonsense") == ()


def test_serving_scope_grants_explicit_policy_is_bounded():
    """An explicit policy call returns the bounded grants (project scope), never a wildcard."""
    grants = serving_scope_grants(ROLE_IMPLEMENTATION, policy=SERVING_SCOPE_POLICY)
    assert grants == ("agentic-dynamics",)
    # The run's own emitted-findings scope is supplied by the caller as a run-derived
    # ``lineage_scope`` and prepended.
    with_run = serving_scope_grants(
        ROLE_PLANNING, policy=SERVING_SCOPE_POLICY, lineage_scope="self-wt-abc"
    )
    assert with_run == ("self-wt-abc", "agentic-dynamics")
    # The literal run-findings placeholder never leaks into a grant when unresolved.
    assert RUN_FINDINGS_SCOPE_TOKEN not in with_run
    assert RUN_FINDINGS_SCOPE_TOKEN not in serving_scope_grants(
        ROLE_PLANNING, policy=SERVING_SCOPE_POLICY
    )


def test_serving_scope_grants_token_requires_a_lineage_scope_not_a_name():
    """u1 (retrieval_serving R2): ``<run-findings>`` is PROOF-CARRYING.

    The token substitutes ONLY from the caller-supplied, run-derived ``lineage_scope``; with
    none it is WITHHELD. A bare NAME — including the retired ``run_scope`` argument — is never
    an ownership proof, so a custom/reused destination (``team-findings``) and even a
    ``self-``-looking name cannot smuggle foreign-run findings into "own findings".
    """
    # A run-derived lineage scope substitutes the placeholder.
    assert serving_scope_grants(
        ROLE_REVIEW, policy=SERVING_SCOPE_POLICY, lineage_scope="self-this-run"
    ) == ("self-this-run",)
    # With NO lineage scope the token is WITHHELD (never a fabricated grant)...
    assert serving_scope_grants(ROLE_REVIEW, policy=SERVING_SCOPE_POLICY) == ()
    # ...even when an arbitrary/custom or self-looking name is offered via the RETIRED
    # ``run_scope`` argument: the name denylist is not the ownership predicate.
    assert (
        serving_scope_grants(ROLE_REVIEW, policy=SERVING_SCOPE_POLICY, run_scope="team-findings")
        == ()
    )
    assert (
        serving_scope_grants(ROLE_REVIEW, policy=SERVING_SCOPE_POLICY, run_scope="self-this-run")
        == ()
    )
    # The placeholder itself is never returned as a literal grant.
    assert RUN_FINDINGS_SCOPE_TOKEN not in serving_scope_grants(
        ROLE_PLANNING, policy=SERVING_SCOPE_POLICY
    )


def test_serving_scope_grants_trusted_lineage_not_an_environment_derived_name():
    """u2 (retrieval_serving round 3): the token substitutes ONLY from a trusted lineage.

    The round-3 derive-or-withhold rule: ``<run-findings>`` is an ownership CLAIM, and a bare
    NAME in ANY shape is not an ownership proof. The SAME string offered through the trusted
    ``lineage_scope`` channel substitutes, while offered through the retired ``run_scope`` name
    channel it is IGNORED — the CHANNEL, never the name's shape, is the predicate. This is the
    exact discriminator that closes the R2 [P1] leak, where an environment-derived telemetry
    name was treated as a destination proof.
    """
    # The acceptance case: a caller-vouched lineage substitutes the token verbatim.
    assert serving_scope_grants(
        ROLE_REVIEW, policy=SERVING_SCOPE_POLICY, lineage_scope="run-x"
    ) == ("run-x",)
    # The runner's environment-derived telemetry namespace: as a BARE NAME it is ignored and
    # the token is withheld, so two unrelated runs cannot share it through this channel.
    derived_namespace = "self-wf_retrieval_serving_deepseek-flash"
    assert (
        serving_scope_grants(ROLE_REVIEW, policy=SERVING_SCOPE_POLICY, run_scope=derived_namespace)
        == ()
    )
    # The SAME string, vouched for by the caller as the run's OWN lineage, substitutes: the
    # channel is the proof, not the string.
    assert serving_scope_grants(
        ROLE_REVIEW, policy=SERVING_SCOPE_POLICY, lineage_scope=derived_namespace
    ) == (derived_namespace,)
    # A self-looking bare name is ignored too, and empty lineage withholds even when the
    # retired ``run_scope`` names a destination.
    assert serving_scope_grants(ROLE_REVIEW, policy=SERVING_SCOPE_POLICY, run_scope="self-x") == ()
    assert (
        serving_scope_grants(
            ROLE_REVIEW,
            policy=SERVING_SCOPE_POLICY,
            lineage_scope="",
            run_scope=PROJECT_KNOWLEDGE_SCOPE,
        )
        == ()
    )


def test_phase_serving_scopes_rejects_env_derived_telemetry_name():
    """u6 (retrieval_serving round 4, the R2 token contract): the PER-PHASE resolver never
    promotes an environment-derived name to run identity.

    The runner's telemetry fallback has exactly the shape ``self-wf_<spec>_<model>``. Offered
    through the retired ``run_scope`` NAME channel it is IGNORED (the token is withheld); offered
    through the trusted ``lineage_scope`` channel the SAME string substitutes — the CHANNEL, not
    the name's shape, is the ownership predicate. This is the discriminator that closes the R2
    [P1] leak on the ``phase_serving_scopes`` path (a regression that re-consults ``run_scope``
    re-serves the telemetry namespace and fails the ignored-channel assertion).
    """
    policy = {"serving_scope_policy": "default"}
    telemetry = "self-wf_retrieval_serving_deepseek-flash"
    # The exact telemetry shape via the retired NAME channel is ignored -> withheld.
    assert phase_serving_scopes(policy, role=ROLE_REVIEW, run_scope=telemetry) == ()
    # The SAME string vouched for by the caller through lineage_scope substitutes verbatim.
    assert phase_serving_scopes(policy, role=ROLE_REVIEW, lineage_scope=telemetry) == (telemetry,)
    # Empty lineage withholds even when a bare destination name is offered.
    assert (
        phase_serving_scopes(policy, role=ROLE_REVIEW, lineage_scope="", run_scope=telemetry) == ()
    )
    # The no-hint route default remains the promoted default (); routing never applies policy.
    assert resolve_phase_layers("prior", "agent").shared_scopes == ()


def test_phase_serving_scopes_forwards_the_trusted_lineage_scope():
    """u2 (retrieval_serving round 3): ``phase_serving_scopes`` forwards ``lineage_scope`` to
    the role grant, ignores the retired ``run_scope`` name, and leaves the no-hint default ()."""
    policy = {"serving_scope_policy": "default"}
    # A trusted lineage is forwarded to the role's run-findings grant.
    assert phase_serving_scopes(policy, role=ROLE_REVIEW, lineage_scope="run-x") == ("run-x",)
    # Empty lineage withholds even when the retired ``run_scope`` names a destination...
    assert (
        phase_serving_scopes(policy, role=ROLE_REVIEW, lineage_scope="", run_scope="team-findings")
        == ()
    )
    # ...and the legacy name is NEVER forwarded as an ownership proof.
    assert phase_serving_scopes(policy, role=ROLE_REVIEW, run_scope="run-x") == ()
    # The no-hint route default stays () (the policy is never applied implicitly).
    assert resolve_phase_layers("prior", "agent").shared_scopes == ()


def test_phase_serving_scopes_lineage_scope_gates_the_token():
    """u1 (retrieval_serving R2): ``phase_serving_scopes`` forwards ``lineage_scope`` and the
    token is withheld for a role with no lineage scope (the legacy ``run_scope`` is ignored)."""
    policy = {"serving_scope_policy": "default"}
    assert phase_serving_scopes(policy, role=ROLE_REVIEW, lineage_scope="self-wt") == ("self-wt",)
    assert phase_serving_scopes(policy, role=ROLE_REVIEW) == ()
    assert phase_serving_scopes(policy, role=ROLE_REVIEW, run_scope="team-findings") == ()
    assert phase_serving_scopes(policy, role=ROLE_IMPLEMENTATION, lineage_scope="self-wt") == (
        "self-wt",
        "agentic-dynamics",
    )


def test_serving_scope_grants_refuses_wildcards_and_dedupes():
    """A wildcard in a policy entry is refused; empties drop; duplicates collapse."""
    policy = {ROLE_IMPLEMENTATION: ("*", "global", "all", " agentic-dynamics ", "agentic-dynamics")}
    assert serving_scope_grants(ROLE_IMPLEMENTATION, policy=policy) == ("agentic-dynamics",)
    # The declared table itself names no wildcard.
    for grants in SERVING_SCOPE_POLICY.values():
        assert not ({"*", "global", "all"} & set(grants))


def test_serving_scope_policy_does_not_change_no_hint_default():
    """The promoted no-hint route stays `shared_scopes == ()` (policy is opt-in only)."""
    route = resolve_phase_layers("prior", "agent")
    assert route.shared_scopes == ()
    assert route.role == ROLE_PLANNING  # the role that HAS a policy...
    # ...but resolving the route never applies the policy implicitly.
    shape = resolve_layer_route(route)
    assert shape.shared_repository_ids == ()


def test_phase_serving_scopes_is_default_empty_and_role_bounded():
    """u1 (R1): ``phase_serving_scopes`` is default-empty and resolves ONE role at a time.

    No declaration grants nothing (the policy is opt-in); with the policy, the SAME
    ``rag_params`` resolves the implementation role to run-findings ∪ project knowledge but
    the review role to run-findings only and the unknown role to nothing — the per-phase
    contract, never a run-wide union. The no-hint route default stays ``()`` because
    ``resolve_phase_layers`` never consults the policy.
    """
    # Default-empty: no policy and no run-wide list -> nothing, for every role.
    assert phase_serving_scopes({}, role=ROLE_IMPLEMENTATION) == ()
    assert phase_serving_scopes({}, role=ROLE_REVIEW) == ()
    assert phase_serving_scopes({}, role=ROLE_UNKNOWN) == ()
    # With the policy, each role gets ONLY its own bounded grant (lineage_scope substitutes the
    # run-findings placeholder).
    policy = {"serving_scope_policy": "default"}
    assert phase_serving_scopes(policy, role=ROLE_IMPLEMENTATION, lineage_scope="self-wt") == (
        "self-wt",
        "agentic-dynamics",
    )
    assert phase_serving_scopes(policy, role=ROLE_REVIEW, lineage_scope="self-wt") == ("self-wt",)
    assert phase_serving_scopes(policy, role=ROLE_UNKNOWN, lineage_scope="self-wt") == ()
    # The unresolved run-findings placeholder never leaks.
    assert RUN_FINDINGS_SCOPE_TOKEN not in phase_serving_scopes(
        policy, role=ROLE_REVIEW, lineage_scope=""
    )
    # The no-hint route default is UNCHANGED (routing never applies the policy implicitly).
    assert resolve_phase_layers("prior", "agent").shared_scopes == ()


def test_phase_serving_scopes_explicit_grants_override_the_policy():
    """u4 (retrieval_serving R4): ``serving_scope_grants`` is the EXPLICIT-LIST OVERRIDE.

    When the key is supplied — including an EMPTY list — ``phase_serving_scopes`` returns the
    normalized explicit list and does NOT consult the policy selector. The R1 per-phase refactor
    had made the policy grants additive, so a restrictive explicit list could not override a
    broad policy; restoring the documented precedence is the repair. The separate
    ``shared_history_scopes`` channel stays role-independent and is never dropped.
    """
    # (a) An explicit EMPTY list overrides the policy: implementation would otherwise get
    # run-findings ∪ project knowledge, but the deliberate no-grant declaration wins.
    empty = {SERVING_SCOPE_GRANTS_KEY: [], "serving_scope_policy": "default"}
    assert phase_serving_scopes(empty, role=ROLE_IMPLEMENTATION, lineage_scope="self-wt") == ()
    # A restrictive explicit list returns EXACTLY its entries — never the policy grants.
    restrictive = {SERVING_SCOPE_GRANTS_KEY: ["impl-private"], "serving_scope_policy": "default"}
    resolved = phase_serving_scopes(restrictive, role=ROLE_IMPLEMENTATION, lineage_scope="self-wt")
    assert resolved == ("impl-private",)
    assert PROJECT_KNOWLEDGE_SCOPE not in resolved
    assert "self-wt" not in resolved  # the policy's run-findings grant is NOT merged in
    # The override is role-independent: the SAME explicit list is returned for EVERY role.
    for role in (ROLE_PLANNING, ROLE_IMPLEMENTATION, ROLE_REVIEW, ROLE_UNKNOWN):
        assert phase_serving_scopes(restrictive, role=role, lineage_scope="self-wt") == (
            "impl-private",
        )
    # (b) The separate ``shared_history_scopes``/alias channel is role-independent and is NOT
    # dropped by the override — only the policy grants are.
    combined = {
        SERVING_SCOPE_GRANTS_KEY: ["impl-private"],
        "shared_history_scopes": ["shared-x"],
        "serving_scope_policy": "default",
    }
    assert phase_serving_scopes(combined, role=ROLE_IMPLEMENTATION, lineage_scope="self-wt") == (
        "shared-x",
        "impl-private",
    )
    # (c) WITHOUT the explicit key the policy still applies (the override is keyed on presence).
    policy_only = {"serving_scope_policy": "default"}
    assert phase_serving_scopes(policy_only, role=ROLE_IMPLEMENTATION, lineage_scope="self-wt") == (
        "self-wt",
        PROJECT_KNOWLEDGE_SCOPE,
    )
    # A wildcard inside the explicit list is still refused by the normalizing channel.
    wild = {SERVING_SCOPE_GRANTS_KEY: ["*", "global", "all", "impl-private"]}
    assert phase_serving_scopes(wild, role=ROLE_IMPLEMENTATION, lineage_scope="self-wt") == (
        "impl-private",
    )


def _shaped_augment(route, *, retrieve_fn, construct_fn, shared_scopes=None):
    return augment_prompt(
        base_prompt="implement the widget",
        goal="build a widget",
        phase_def={"name": "execute", "kind": "agent"},
        model="deepseek/deepseek-flash",
        commit_sha="abc1234",
        inherited_tools=["read", "edit"],
        pinned_policy="policy",
        rag_params={"repository_id": "self-wt"},
        retrieve_fn=retrieve_fn,
        construct_fn=construct_fn,
        route=route,
        shared_scopes=shared_scopes,
    )


def test_augment_emits_context_route_with_one_disposition_per_layer():
    """A real route yields a layer disposition; served ids carry a layer; L4 is refused."""
    route = resolve_phase_layers("execute", "agent")
    seen: dict[str, object] = {}
    received: dict[str, list[str]] = {}

    def retrieve_fn(**kwargs):
        seen.update(kwargs)
        return _FakeAttempt(
            [_FakeCandidate("k-code", "code"), _FakeCandidate("k-belief", "belief")]
        )

    def construct_fn(request):
        # A deterministic constructor renders EXACTLY the evidence it receives, so the test
        # can prove whether the prohibited belief ever reached construction or the prompt.
        received["ids"] = [unit.knowledge_id for unit in request.evidence]
        received["texts"] = [unit.text for unit in request.evidence]
        constructed = _FakeConstructed(list(received["ids"]))
        constructed.prompt = "AUGMENTED PROMPT\n" + "\n".join(received["texts"])
        return constructed

    outcome = _shaped_augment(
        route, retrieve_fn=retrieve_fn, construct_fn=construct_fn, shared_scopes=["shared-1"]
    )

    # R1: the valid belief candidate is refused BEFORE construction — its id and text are
    # absent from the constructor input AND from the final prompt.
    assert "k-belief" not in received["ids"]
    assert "text for k-belief" not in received["texts"]
    assert "k-belief" not in outcome.prompt
    assert "text for k-belief" not in outcome.prompt
    assert "k-code" in received["ids"]

    assert outcome.context_route is not None
    record = outcome.context_route
    assert record["schema"] == "context-route/v1"
    assert record["route_status"] == "resolved"
    assert record["shared_scopes"] == ["shared-1"]

    by_layer = {entry["layer"]: entry for entry in record["layers"]}
    # One disposition per resolved layer (L3 was not resolved for an implementation phase).
    assert {"L0", "L1", "L2"} <= set(by_layer)
    assert by_layer["L1"]["status"] == LAYER_STATUS_SERVED
    assert by_layer["L1"]["evidence_ids"] == ["k-code"]
    # L2 history resolved but nothing matched on a clean pass: empty, never served.
    assert by_layer["L2"]["status"] == "empty"
    # The refused self-layer content is recorded excluded with its id and never counted served.
    assert by_layer[LAYER_SELF]["status"] == LAYER_STATUS_EXCLUDED
    assert by_layer[LAYER_SELF]["evidence_ids"] == ["k-belief"]
    assert record["served_count"] == 1

    # The route actually shaped retrieval: source types were threaded, shared scope too.
    assert "code" in seen["source_types"]
    assert "story" in seen["source_types"]
    assert list(seen["shared_repository_ids"]) == ["shared-1"]


def test_augment_refuses_l4_before_construction_on_unrouted_paths():
    """R1: under an ABSENT or explicit-UNKNOWN route, a self candidate never reaches the
    constructor input or the final prompt; its id is recorded excluded; the base prompt and
    the raw work item are preserved, and nothing is served."""
    for route in (None, LayerRoute.unknown("execute", "agent")):
        received: dict[str, object] = {}

        def retrieve_fn(**_kwargs):
            return _FakeAttempt([_FakeCandidate("k-belief", "belief")])

        def construct_fn(request, received=received):
            received["ids"] = [unit.knowledge_id for unit in request.evidence]
            received["raw"] = request.raw_work_item
            constructed = _FakeConstructed(list(received["ids"]))
            constructed.prompt = "AUGMENTED PROMPT\n" + "\n".join(
                unit.text for unit in request.evidence
            )
            return constructed

        outcome = _shaped_augment(route, retrieve_fn=retrieve_fn, construct_fn=construct_fn)

        # The belief never reached the constructor, and its text is not in the final prompt.
        assert received["ids"] == []
        assert "text for k-belief" not in outcome.prompt
        assert "k-belief" not in outcome.prompt
        # The base prompt (raw work item) still reached construction unchanged.
        assert received["raw"] == "implement the widget"

        record = outcome.context_route
        assert record is not None
        assert record["served_count"] == 0
        by_layer = {entry["layer"]: entry for entry in record["layers"]}
        assert by_layer[LAYER_SELF]["status"] == LAYER_STATUS_EXCLUDED
        assert by_layer[LAYER_SELF]["evidence_ids"] == ["k-belief"]


def test_augment_names_layer_absent_on_leg_failure():
    """A failed leg is a NAMED absence for the layer, never an empty success."""
    route = resolve_phase_layers("execute", "agent")

    def retrieve_fn(**_kwargs):
        return _FakeAttempt([], leg_errors={"dense": "connection refused"})

    def construct_fn(_request):
        return _FakeConstructed([])

    outcome = _shaped_augment(route, retrieve_fn=retrieve_fn, construct_fn=construct_fn)

    record = outcome.context_route
    assert record is not None
    by_layer = {entry["layer"]: entry for entry in record["layers"]}
    assert by_layer["L1"]["status"] == LAYER_STATUS_NAMED_ABSENT
    assert by_layer["L2"]["status"] == LAYER_STATUS_NAMED_ABSENT
    assert by_layer["L1"]["status"] != LAYER_STATUS_SERVED
    assert record["leg_errors"] == {"dense": "connection refused"}
    assert record["served_count"] == 0


def test_augment_unknown_route_records_unclassified_never_served():
    """An unroutable request records its served items as UNKNOWN; nothing is served unclassified."""

    def retrieve_fn(**_kwargs):
        return _FakeAttempt([_FakeCandidate("k-code", "code")])

    def construct_fn(_request):
        return _FakeConstructed(["k-code"])

    outcome = _shaped_augment(None, retrieve_fn=retrieve_fn, construct_fn=construct_fn)

    record = outcome.context_route
    assert record is not None
    assert record["route_status"] == "unknown"
    assert record["role"] == "unknown"
    assert record["served_count"] == 0
    assert [item["id"] for item in record["unclassified"]] == ["k-code"]
    by_layer = {entry["layer"]: entry for entry in record["layers"]}
    assert by_layer["unclassified"]["status"] == "unknown"


def test_augment_always_populates_context_route_on_retrieve_failure():
    """Even the no-rag fallback carries a context_route record and preserves base_prompt."""

    def fail_retrieve(**_kwargs):
        raise RuntimeError("retrieval unavailable")

    def should_not_construct(_request):
        raise AssertionError("a retrieval failure must not invoke construction")

    outcome = _shaped_augment(
        resolve_phase_layers("execute", "agent"),
        retrieve_fn=fail_retrieve,
        construct_fn=should_not_construct,
    )

    assert outcome.prompt == "implement the widget"
    assert outcome.fallback is True
    assert outcome.context_route is not None
    assert outcome.context_route["served_count"] == 0
    by_layer = {entry["layer"]: entry for entry in outcome.context_route["layers"]}
    assert by_layer["L1"]["status"] == LAYER_STATUS_NAMED_ABSENT


def test_augment_withholds_untyped_evidence_on_unresolved_route():
    """A8-R1: on a route that resolved NO layers, untyped evidence never reaches the
    constructor input or the final prompt; it is recorded as an honest withheld/unknown
    disposition while typed items keep their unclassified-but-served behavior; the base
    prompt is preserved.

    Falsifier for the exact defect: an untyped candidate (``source_type=""``) plus a typed
    ``code`` candidate and a ``source_type_resolver`` leg error, under BOTH ``route=None``
    and ``LayerRoute.unknown(...)``. The deterministic constructor renders EXACTLY the
    evidence it receives, so the absence assertion proves the withhold. Removing the
    withhold would leave the untyped candidate in ``request.evidence`` and the prompt.
    """
    for route in (None, LayerRoute.unknown("execute", "agent")):
        received: dict[str, object] = {}

        def retrieve_fn(**_kwargs):
            return _FakeAttempt(
                [_FakeCandidate("k-untyped", ""), _FakeCandidate("k-code", "code")],
                leg_errors={
                    SOURCE_TYPE_RESOLVER_ERROR_KEY: "resolver raised for candidate 'k-untyped'"
                },
            )

        def construct_fn(request, received=received):
            # Render EXACTLY the evidence this constructor RECEIVES, so the assertions can
            # prove whether the untyped candidate ever reached construction or the prompt.
            received["ids"] = [unit.knowledge_id for unit in request.evidence]
            received["texts"] = [unit.text for unit in request.evidence]
            constructed = _FakeConstructed(list(received["ids"]))
            constructed.prompt = (
                "AUGMENTED PROMPT\n"
                + str(request.raw_work_item)
                + "\n"
                + "\n".join(received["texts"])
            )
            return constructed

        outcome = _shaped_augment(route, retrieve_fn=retrieve_fn, construct_fn=construct_fn)

        # The untyped candidate never reached the constructor input...
        assert "k-untyped" not in received["ids"]
        assert "text for k-untyped" not in received["texts"]
        # ...nor the final prompt; the typed candidate may still be served.
        assert "k-untyped" not in outcome.prompt
        assert "text for k-untyped" not in outcome.prompt
        assert "k-code" in received["ids"]
        assert "text for k-code" in outcome.prompt
        # The base prompt is preserved, never replaced by the augmentation.
        assert "implement the widget" in outcome.prompt

        record = outcome.context_route
        assert record is not None
        assert record["route_status"] == "unknown"
        assert record["served_count"] == 0
        # The withheld id is recorded with an honest unknown/withheld disposition naming it.
        withheld = [item for item in record["unclassified"] if item["id"] == "k-untyped"]
        assert len(withheld) == 1
        assert withheld[0]["status"] == "unknown"
        assert withheld[0]["reason"] == UNRESOLVED_WITHHELD_REASON
        assert "withheld" in withheld[0]["reason"]
        # The typed item keeps its unclassified-but-served behavior; nothing is silently dropped.
        assert "k-code" in [item["id"] for item in record["unclassified"]]
        # The synthetic unclassified layer entry lists every unclassified/withheld id.
        by_layer = {entry["layer"]: entry for entry in record["layers"]}
        assert by_layer["unclassified"]["status"] == "unknown"
        assert set(by_layer["unclassified"]["evidence_ids"]) == {"k-untyped", "k-code"}
        # The resolver diagnostic survives in the record alongside the withhold.
        assert SOURCE_TYPE_RESOLVER_ERROR_KEY in record["leg_errors"]
