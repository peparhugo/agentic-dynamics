"""Tests for the prompt-constructor: schema validation, constraint/citation/tool checks,
one-repair, deterministic fallback, and no-fork keying."""

import json
from dataclasses import fields

from agentic_dynamics.knowledge.augment import augment_prompt
from agentic_dynamics.knowledge.context_layers import (
    LAYER_SELF,
    LAYER_STATUS_EXCLUDED,
    LAYER_STATUS_NAMED_ABSENT,
    LAYER_STATUS_SERVED,
    UNRESOLVED_WITHHELD_REASON,
    LayerRoute,
    resolve_layer_route,
    resolve_phase_layers,
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
    assert DEFAULT_CONSTRUCTOR_MODEL == "deepseek/deepseek-v4-flash"


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
