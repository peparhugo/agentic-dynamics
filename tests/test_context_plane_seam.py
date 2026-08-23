"""Tests for CAP I7 — the apply seam (``control.rules.make_applying_router``, kept OFF by default).

Covers ``make_applying_router`` in isolation (applies the plane's ``route`` choice only when a
freshly re-validated decision is admitted; falls back to the deterministic baseline on an
inadmissible snapshot, a ``continue`` proposal, a C1-C10 refusal, or any internal exception —
"the fallback IS the safe path"), the shadow-bookkeeping it still records
(``parameters.applied``), and an end-to-end ``runtime.workflow_runner.run_workflow()`` fixture
proving the seam actually changes which model executes a phase when injected and valid, and
changes nothing when it is not injected (the default) — the per-spec
``workflow.params.control_route`` opt-in ``scripts/run_workflow.py`` gates on.
"""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

from agentic_dynamics.control.context_compiler import (
    ContextRequest,
    InMemoryFactStore,
    compile_context,
)
from agentic_dynamics.control.facts import (
    EPISTEMIC_MAP,
    FACT_PREDICATES,
    CanonicalFact,
    recompute_inputs_digest,
)
from agentic_dynamics.control.rules import (
    make_applying_router,
    record_shadow_decision,
    route_next_job_v1,
)
from agentic_dynamics.experiment.experiment_spec import ExperimentSpec, Factor, Workflow
from agentic_dynamics.runtime.routing import RouteState, RoutingPreferences
from agentic_dynamics.runtime.workflow_runner import run_workflow

NOW = "2026-08-23T00:00:00+00:00"
REPO = "agentic-dynamics"
WORKLOAD = "cap_i7_demo"
CELL = "wf_cap_i7_demo_cell"
JOB_SCOPE = f"org:{REPO}/workload:{WORKLOAD}/job:{CELL}"
WORKFLOW_SCOPE = f"org:{REPO}/workload:{WORKLOAD}/workflow:{CELL}"
WORKLOAD_SCOPE = f"org:{REPO}/workload:{WORKLOAD}"

MODEL_A = "anthropic/claude-haiku-4-5"  # lexicographically first — the plane's pick
MODEL_B = "anthropic/claude-sonnet-5"  # pool[0] under a cold-start router — the baseline pick


def _fact(*, predicate, value, scope_type, scope_id, scope_path, fact_id,
          reducer_version="workflow_facts/v1", epistemic_status="derived"):
    spec = FACT_PREDICATES[predicate]
    authority, evidence_class = EPISTEMIC_MAP[epistemic_status]
    fact = CanonicalFact(
        fact_entity_id=f"entity_{predicate}_{scope_id}", fact_id=fact_id,
        subject_type=spec.subject_type, subject_id=scope_id, predicate=predicate, value=value,
        value_type=spec.value_type, unit=spec.unit, scope_type=scope_type, scope_id=scope_id,
        scope_path=scope_path, abstraction_level=spec.abstraction_level,
        epistemic_status=epistemic_status, authority=authority, evidence_class=evidence_class,
        observed_at=NOW, valid_from=NOW, valid_to=None, expires_at=None,
        reducer=reducer_version.split("/")[0], reducer_version=reducer_version, evidence_ids=(),
        inputs_digest="", supersedes=None, source_revision="abc123", repository_id=REPO,
        lifecycle_state="current",
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


def _admissible_store(remaining: str = "2") -> InMemoryFactStore:
    return InMemoryFactStore(facts=(
        _fact(predicate="job_accumulated_cost_usd", value="1.0", scope_type="job",
              scope_id=CELL, scope_path=JOB_SCOPE, reducer_version="job_facts/v1",
              epistemic_status="observed", fact_id="fact_cost"),
        _fact(predicate="workflow_phases_remaining", value=remaining, scope_type="workflow",
              scope_id=CELL, scope_path=WORKFLOW_SCOPE, reducer_version="workflow_facts/v1",
              fact_id="fact_remaining"),
        _fact(predicate="allowed_models", value=f"{MODEL_B},{MODEL_A}", scope_type="workload",
              scope_id=WORKLOAD, scope_path=WORKLOAD_SCOPE, reducer_version="policy_facts/v1",
              epistemic_status="declared", fact_id="fact_allowed_models"),
        _fact(predicate="max_spend_usd", value="50.0", scope_type="workload", scope_id=WORKLOAD,
              scope_path=WORKLOAD_SCOPE, reducer_version="policy_facts/v1",
              epistemic_status="declared", fact_id="fact_max_spend"),
    ))


def _now_fixed() -> str:
    return NOW


def _router(store, *, record=False):
    # record=False by default in these tests: make_applying_router's real recording path
    # (record_snapshot/record_shadow_decision) writes to the REAL KB_ARTIFACT_DIR when not
    # explicitly isolated, and these tests care about the ROUTING decision, not persistence —
    # see test_shadow_bookkeeping_records_the_applied_flag for an isolated (tmp_path) direct
    # test of the recording path itself.
    return make_applying_router(
        workload=WORKLOAD, cell_id=CELL, repository_id=REPO, store=store, record=record,
        now_fn=_now_fixed,
    )


# ── make_applying_router in isolation ─────────────────────────────


def _call(router, pool):
    return router({}, RouteState(pool=pool), RoutingPreferences(), signals={})


def test_applies_the_plane_choice_when_admissible_and_route():
    router = _router(_admissible_store())
    chosen = _call(router, [MODEL_B, MODEL_A])
    assert chosen == MODEL_A  # the plane's pick — NOT pool[0] (route_step's cold-start baseline)


def test_falls_back_when_snapshot_is_inadmissible():
    store = InMemoryFactStore(
        facts=tuple(f for f in _admissible_store().facts if f.predicate != "allowed_models")
    )
    router = _router(store)
    chosen = _call(router, [MODEL_B, MODEL_A])
    assert chosen == MODEL_B  # route_step's cold-start baseline — the plane had nothing to say


def test_falls_back_when_the_decision_is_continue():
    router = _router(_admissible_store(remaining="0"))  # no phases remaining -> continue
    chosen = _call(router, [MODEL_B, MODEL_A])
    assert chosen == MODEL_B


def test_falls_back_on_any_internal_exception(monkeypatch):
    import agentic_dynamics.control.rules as rules_mod

    def _boom(*a, **k):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(rules_mod, "compile_context", _boom)
    router = _router(_admissible_store())
    chosen = _call(router, [MODEL_B, MODEL_A])
    assert chosen == MODEL_B  # the safe path, unchanged


def test_never_raises_past_the_seam(monkeypatch):
    import agentic_dynamics.control.rules as rules_mod

    monkeypatch.setattr(
        rules_mod, "compile_context", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
    )
    router = _router(_admissible_store())
    # Must not raise.
    _call(router, [MODEL_B, MODEL_A])


def test_shadow_bookkeeping_records_the_applied_flag(tmp_path):
    # Isolated (tmp_path) direct exercise of the recording path itself — record_shadow_decision
    # already takes an explicit artifact_dir, so no real repository files are touched.
    request = ContextRequest(
        decision_type="route_next_job", scope_type="job", scope_id=CELL, scope_path=JOB_SCOPE,
        repository_id=REPO,
    )
    ctx = compile_context(request, store=_admissible_store(), now=NOW)
    decision = route_next_job_v1(ctx, target_id=CELL, proposed_at=NOW)
    assert decision.action == "route"
    decision = replace(
        decision,
        parameters={
            **decision.parameters, "applied": True, "baseline_action": "route",
            "baseline_model": MODEL_B,
        },
    )
    record = record_shadow_decision(
        decision, repository_id=REPO, causes="deadbeef" * 4, artifact_dir=tmp_path
    )
    assert record is not None
    artifact = json.loads((tmp_path / f"{record.knowledge_id}.json").read_text())
    body = json.loads(artifact["text"])
    assert body["requested_action"]["parameters"]["applied"] is True
    assert body["requested_action"]["parameters"]["model"] == MODEL_A


def test_recording_disabled_still_applies():
    router = _router(_admissible_store(), record=False)
    chosen = _call(router, [MODEL_B, MODEL_A])
    assert chosen == MODEL_A


# ── End to end: run_workflow() with the seam injected ─────────────


def _fake_agent_recording(seen_models):
    def agent(prompt, *, model, backend, workdir, **kwargs):
        seen_models.append(model)
        return SimpleNamespace(
            prompt_tokens=1, completion_tokens=1, reasoning_tokens=0, total_tokens=2,
            estimated_cost_usd=0.0, files_created=[], files_modified=[], final_response="",
            ok=True, exit_code=0, error="", session_id="sess_1",
            cache_read_tokens=0, cache_write_tokens=0, cache_hit_rate=0.0,
        )

    return agent


def _seam_spec() -> ExperimentSpec:
    phases = [{"name": "only", "kind": "agent", "prompt": "p"}]
    return ExperimentSpec(
        name="cap_i7_seam_test", question="q", version="1",
        workflow=Workflow("agent_task", {
            "language": "python", "model_pool": [MODEL_B, MODEL_A], "phases": phases,
            "control_route": True,  # the per-spec opt-in scripts/run_workflow.py reads
        }),
        factors=[Factor("model", [MODEL_B])], design="factorial",
    )


def test_run_workflow_applies_the_plane_choice_when_the_seam_is_injected(tmp_path):
    spec = _seam_spec()
    seen_models: list[str] = []
    router = _router(_admissible_store())
    run_workflow(
        spec, goal="g", model=MODEL_B, workdir=tmp_path, commit=False,
        run_agentic_fn=_fake_agent_recording(seen_models), router=router,
    )
    assert seen_models == [MODEL_A]  # the plane's choice actually executed the phase


def test_run_workflow_without_the_seam_keeps_the_deterministic_router(tmp_path):
    from agentic_dynamics.control.step_routing import route_step

    spec = _seam_spec()
    seen_models: list[str] = []
    run_workflow(
        spec, goal="g", model=MODEL_B, workdir=tmp_path, commit=False,
        run_agentic_fn=_fake_agent_recording(seen_models), router=route_step,
    )
    assert seen_models == [MODEL_B]  # unchanged — the seam was never injected


def test_no_committed_spec_opts_into_control_route():
    """Design §9 I7's own gate: the opt-in ships OFF, and nothing flips it — verified over the
    real committed spec corpus, not just this test's own fixture."""
    from pathlib import Path

    from agentic_dynamics.experiment.experiment_spec import load_spec

    repo_root = Path(__file__).resolve().parent.parent
    paths = sorted((repo_root / "experiments" / "definitions").glob("*.yaml"))
    paths += sorted((repo_root / "workflows").rglob("*.yaml"))
    offenders = [
        p for p in paths if bool(load_spec(p).workflow.params.get("control_route", False))
    ]
    assert offenders == []
