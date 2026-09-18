"""Unit 4B — approved knowledge reaches the exact worker context (deterministic).

The delivery contract at the real seams, with no live services:

* an explicitly scoped delivery spec keeps its public scope through ``_resolve_rag_params``
  (the private cell-scope default is for UNSCOPED discovery, never a declared delivery);
* the REAL ``retrieve()`` applies repository + ACL filters: an approved public finding is
  selected; a private coordinator record and a wrong-repository record are excluded;
* the REAL deterministic renderer places the approved finding's text into the prompt handed
  to the executor — the exact prepared worker context — with the private text absent;
* pinned constraints ride the authoritative block, retrieved evidence the untrusted block;
* the run result records selected IDs, their revisions/source types, and the fallback mode,
  and distinguishes unavailable (``no_rag``) from genuinely empty (``full``).
"""

from __future__ import annotations

import functools
import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src", _ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from agentic_dynamics.experiment.experiment_spec import load_spec  # noqa: E402
from agentic_dynamics.knowledge.prompt_constructor import (  # noqa: E402
    AugmentedPrompt,
    PromptPlan,
    hash_work_item,
    render_prompt,
)
from agentic_dynamics.knowledge.retrieval import retrieve  # noqa: E402
from agentic_dynamics.runtime.workflow_runner import (  # noqa: E402
    _resolve_rag_params,
    run_workflow,
)

APPROVED = "APPROVED-MARKER the render gate requires captured screenshots at both viewports"
PRIVATE = "PRIVATE-MARKER the coordinator's private session reflection"
PINNED = "PINNED-CONSTRAINT: render only packet-emitted values; never fabricate a value"

SPEC_YAML = f"""
name: delivery_context_fixture
question: >-
  Fixture: approved knowledge must reach the prepared worker prompt; private coordinator
  records must not.
version: "0.1"
artifact_kind: workflow
intent: mutate
side_effects:
  repository: true
  external_services: false
repeatable: true
factors:
  - {{name: model, levels: [deepseek/deepseek-v4-flash]}}
design: factorial
rules: []
metrics: []
comparison: null
writeup: {{format: lab_book, sections: [question, deliver]}}
stop: {{budget_usd: 0.01, max_attempts: 1}}
adapt: {{strategy: manual, selection: highest_regret}}
workflow:
  kind: agent_task
  params:
    language: python
    rag_augment: true
    rag:
      repository_id: agentic-dynamics
      acl_scope: public
      pattern_projection: false
      emit_self: false
      pinned_policy: "{PINNED}"
    phases:
      - name: deliver
        kind: agent
        timeout: 60
        prompt: |
          GOAL: {{goal}}
          Implement the bounded change.
"""


def _spec(tmp_path: Path):
    spec_path = tmp_path / "delivery_context_fixture.yaml"
    spec_path.write_text(SPEC_YAML)
    return load_spec(spec_path)


def _fake_agent(**overrides):
    base = dict(
        prompt_tokens=10,
        completion_tokens=20,
        reasoning_tokens=5,
        total_tokens=35,
        estimated_cost_usd=0.001,
        files_created=[],
        files_modified=[],
        final_response="done",
        ok=True,
        exit_code=0,
        error="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class _DenseStub:
    def __init__(self, hits=None, *, exc=None):
        self._hits = list(hits or [])
        self._exc = exc

    def search(self, query, *, top_k=10, where=None):
        if self._exc is not None:
            raise self._exc
        return list(self._hits)


class _GraphStub:
    def __init__(self, hits=None):
        self._hits = list(hits or [])

    def search_knowledge_fulltext(self, query, *, limit=10, commit=None):
        return list(self._hits)

    def expand_candidates(self, seeds, **kwargs):
        return []


def _dense_hit(cid: str, text: str, **meta) -> dict:
    metadata = {
        "source_type": "finding",
        "authority": "MEASURED",
        "repository_id": "agentic-dynamics",
        "acl_scope": "public",
        "commit_sha": "",
        "observed_at": "2026-09-01T00:00:00+00:00",
        "logical_locator": f"experiments/results/kb/{cid}.json",
    }
    metadata.update(meta)
    return {"id": cid, "document": text, "metadata": metadata, "distance": 0.1}


def _lex_hit(cid: str, text: str, **props) -> dict:
    properties = {
        "source_type": "meta_session",
        "authority": "ADVISORY",
        "repository_id": "agentic-dynamics",
        "acl_scope": "org:agentic-dynamics",
        "commit_sha": "",
        "observed_at": "2026-09-01T00:00:00+00:00",
        "text": text,
    }
    properties.update(props)
    return {"id": cid, "labels": ["Knowledge"], "properties": properties, "score": 1.0}


def _construct(request):
    """The deterministic renderer at the constructor seam (no model call)."""
    plan = PromptPlan(
        schema_version="prompt-plan/v1",
        task_intent="delivery fixture",
        raw_work_item_hash=hash_work_item(request.raw_work_item),
    )
    prompt = render_prompt(plan, request, request.evidence)
    return AugmentedPrompt(
        prompt=prompt,
        prompt_plan=plan,
        raw_work_item_hash=hash_work_item(request.raw_work_item),
        constructor_model=request.constructor_model,
        schema_version="prompt-plan/v1",
        evidence_ids=[e.knowledge_id for e in request.evidence],
        token_count=0,
        fallback=True,
        repair_count=0,
        validator_errors=[],
    )


def test_delivery_scope_is_explicit_not_the_private_cell_default(tmp_path):
    spec = _spec(tmp_path)
    resolved = _resolve_rag_params(spec, None, wd=tmp_path / "wt_somecell", rag_augment=True)
    assert resolved["repository_id"] == "agentic-dynamics"
    assert resolved["acl_scope"] == "public"


def test_approved_finding_reaches_the_exact_prepared_prompt(tmp_path):
    spec = _spec(tmp_path)
    dense = _DenseStub(
        [
            _dense_hit("k_approved", APPROVED),
            _dense_hit("k_wrongrepo", "WRONG-REPO-MARKER", repository_id="self-other-cell"),
        ]
    )
    graph = _GraphStub([_lex_hit("k_private", PRIVATE)])
    retrieve_fn = functools.partial(
        retrieve, dense_store=dense, graph_client=graph, deadline_s=2.0
    )
    captured: list[str] = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        captured.append(prompt)
        return _fake_agent()

    result = run_workflow(
        spec,
        goal="deliver the bounded change",
        model="m",
        workdir=tmp_path,
        commit=False,
        rag_augment=True,
        retrieve_fn=retrieve_fn,
        construct_fn=_construct,
        run_agentic_fn=agent,
    )

    phase = result.phases[0]
    assert phase.status == "ok", phase.error
    assert captured, "the executor received no prompt"
    prompt = captured[0]

    # Content, not IDs: the approved finding's text IS in the prepared prompt.
    assert APPROVED in prompt
    # The private coordinator record and the wrong-repository record never surface.
    assert PRIVATE not in prompt
    assert "WRONG-REPO-MARKER" not in prompt
    # The pinned constraint rides the authoritative block, above the untrusted evidence.
    assert PINNED in prompt
    assert "Pinned policy" in prompt and "Evidence (untrusted" in prompt
    assert prompt.index(PINNED) < prompt.index(APPROVED)
    # Provenance on the existing run result: IDs + revisions/source types + fallback mode.
    assert phase.selected_evidence_ids == ["k_approved"]
    assert phase.fallback_mode == "full"
    assert phase.augmentation_evidence
    entry = phase.augmentation_evidence[0]
    assert entry["id"] == "k_approved"
    assert entry["source_type"] == "finding"
    # The run-result serialization carries the same evidence block.
    assert result.to_dict()["phases"][0]["augmentation_evidence"] == phase.augmentation_evidence


def test_unavailable_retrieval_is_reported_distinct_from_empty(tmp_path):
    spec = _spec(tmp_path)
    run_a = tmp_path / "run_a"
    run_a.mkdir()
    run_b = tmp_path / "run_b"
    run_b.mkdir()

    def agent(prompt, *, model, backend, workdir, **kwargs):
        return _fake_agent()

    # Both legs unavailable -> named no_rag (never a successful empty search).
    unavailable = run_workflow(
        spec,
        goal="deliver",
        model="m",
        workdir=run_a,
        commit=False,
        rag_augment=True,
        retrieve_fn=functools.partial(retrieve),
        construct_fn=_construct,
        run_agentic_fn=agent,
    )
    assert unavailable.phases[0].fallback_mode == "no_rag"

    # Healthy legs, no applicable evidence -> genuinely empty, full.
    healthy_empty = run_workflow(
        spec,
        goal="deliver",
        model="m",
        workdir=run_b,
        commit=False,
        rag_augment=True,
        retrieve_fn=functools.partial(retrieve, dense_store=_DenseStub([]), graph_client=_GraphStub([])),
        construct_fn=_construct,
        run_agentic_fn=agent,
    )
    assert healthy_empty.phases[0].fallback_mode == "full"
    assert healthy_empty.phases[0].selected_evidence_ids == []


def _construct_trimming(request):
    """The deterministic renderer, simulating a constructor that TRIMS evidence to fit."""
    kept = list(request.evidence)[:1]
    plan = PromptPlan(
        schema_version="prompt-plan/v1",
        task_intent="trim fixture",
        raw_work_item_hash=hash_work_item(request.raw_work_item),
    )
    prompt = render_prompt(plan, request, kept)
    return AugmentedPrompt(
        prompt=prompt,
        prompt_plan=plan,
        raw_work_item_hash=hash_work_item(request.raw_work_item),
        constructor_model=request.constructor_model,
        schema_version="prompt-plan/v1",
        evidence_ids=[e.knowledge_id for e in kept],
        token_count=0,
        fallback=True,
        repair_count=0,
        validator_errors=[],
    )


def test_provenance_follows_the_trimmed_final_selection(tmp_path):
    spec = _spec(tmp_path)
    dense = _DenseStub(
        [_dense_hit("k1", "FIRST-MARKER alpha"), _dense_hit("k2", "SECOND-MARKER beta")]
    )
    graph = _GraphStub([])
    seen: dict[str, int] = {}

    def recording_retrieve(**kwargs):
        attempt = retrieve(**kwargs, dense_store=dense, graph_client=graph, deadline_s=2.0)
        seen["selected"] = len(attempt.selected_evidence)
        return attempt

    captured: list[str] = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        captured.append(prompt)
        return _fake_agent()

    result = run_workflow(
        spec,
        goal="deliver the bounded change",
        model="m",
        workdir=tmp_path,
        commit=False,
        rag_augment=True,
        retrieve_fn=recording_retrieve,
        construct_fn=_construct_trimming,
        run_agentic_fn=agent,
    )
    phase = result.phases[0]
    assert phase.status == "ok", phase.error
    # The retrieval found two; the constructor emitted one (simulated trim).
    assert seen["selected"] == 2
    assert len(phase.selected_evidence_ids) == 1
    trimmed_id = phase.selected_evidence_ids[0]
    # Provenance claims ONLY the emitted source — never the trimmed-away one.
    assert [e["id"] for e in phase.augmentation_evidence] == [trimmed_id]
    emitted_marker = "FIRST-MARKER" if trimmed_id == "k1" else "SECOND-MARKER"
    other_marker = "SECOND-MARKER" if trimmed_id == "k1" else "FIRST-MARKER"
    assert captured and emitted_marker in captured[0]
    assert other_marker not in captured[0]


def test_degraded_leg_causes_reach_the_run_result(tmp_path):
    spec = _spec(tmp_path)
    dense = _DenseStub(exc=RuntimeError("dense backend down"))
    graph = _GraphStub([_lex_hit("k_private", PRIVATE)])

    def agent(prompt, *, model, backend, workdir, **kwargs):
        return _fake_agent()

    result = run_workflow(
        spec,
        goal="deliver",
        model="m",
        workdir=tmp_path,
        commit=False,
        rag_augment=True,
        retrieve_fn=functools.partial(
            retrieve, dense_store=dense, graph_client=graph, deadline_s=2.0
        ),
        construct_fn=_construct,
        run_agentic_fn=agent,
    )
    phase = result.phases[0]
    assert "dense" in phase.retrieval_leg_errors
    assert "dense backend down" in phase.retrieval_leg_errors["dense"]
    assert result.to_dict()["phases"][0]["retrieval_leg_errors"] == phase.retrieval_leg_errors


def test_construction_causes_reach_the_run_result(monkeypatch):
    """Diagnostic acceptance gap: a store that fails to CONSTRUCT must name its cause in
    ``leg_errors`` rather than vanishing into a silent ``None``."""
    from agentic_dynamics.knowledge import augment as aug

    class _BoomChroma:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("chroma init refused")

    class _BoomNeo4j:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("neo4j init refused")

    monkeypatch.setattr("agentic_dynamics.knowledge.embeddings.ChromaStore", _BoomChroma)
    monkeypatch.setattr("agentic_dynamics.knowledge.graph.Neo4jClient", _BoomNeo4j)

    retrieve_fn = aug.default_retrieve_fn()
    attempt = retrieve_fn(
        raw_work_item="q", repository_id="agentic-dynamics", acl_scope="public"
    )
    assert attempt.fallback_mode == "no_rag"
    assert "chroma init refused" in attempt.leg_errors.get("dense", "")
    assert "neo4j init refused" in attempt.leg_errors.get("lexical", "")
