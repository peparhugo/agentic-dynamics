"""Tests for the execute runner — run_workflow drives agent_task phases in a worktree."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from agentic_dynamics.experiment import spec_status
from agentic_dynamics.runtime import workflow_runner
from agentic_dynamics.knowledge.augment import default_retrieve_fn
from agentic_dynamics.experiment.experiment_spec import load_spec, validate_spec
from agentic_dynamics.experiment.spec_status import SpecStatusEntry
from agentic_dynamics.runtime.workflow_runner import (
    _build_phase_prompt,
    _completed_phases_from_index,
    cell_scope,
    run_workflow,
)

SPEC = Path(__file__).resolve().parent.parent / "experiments" / "specs" / "control_room_portal.yaml"


def _fake_agent(**overrides):
    base = dict(
        prompt_tokens=10,
        completion_tokens=20,
        reasoning_tokens=5,
        total_tokens=35,
        estimated_cost_usd=0.001,
        files_created=["docs/scope.md"],
        files_modified=[],
        final_response="done",
        ok=True,
        exit_code=0,
        error="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_spec_loads_and_validates():
    spec = load_spec(SPEC)
    assert spec.name == "control_room_portal"
    assert spec.workflow.kind == "agent_task"
    assert [p["name"] for p in spec.workflow.params["phases"]] == ["scope", "ux_design", "implement", "verify"]
    assert validate_spec(spec) == []


def test_phase_prompt_templating():
    phase = {"name": "scope", "prompt": "Write a scope for {goal}. Prior: {prior_phases}"}
    out = _build_phase_prompt(phase, "the portal", ["scope (ok)"])
    assert "the portal" in out
    assert "scope (ok)" in out
    assert "{goal}" not in out


def test_run_workflow_phases_in_order(tmp_path):
    spec = load_spec(SPEC)
    seen = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        seen.append(prompt.splitlines()[1][:12])  # capture the "Goal: ..." line tail
        return _fake_agent()

    result = run_workflow(spec, goal="the goal", model="openai/gpt-5.6-sol",
                          workdir=tmp_path, commit=False, run_agentic_fn=agent)
    assert [p.phase for p in result.phases] == ["scope", "ux_design", "implement", "verify"]
    assert len(seen) == 3  # scope, ux, implement are agent phases; verify is test
    assert result.phases[0].tokens["total"] == 35
    assert result.phases[0].cost_usd == 0.001


def test_run_workflow_publishes_phase_per_phase(tmp_path, monkeypatch):
    """Each phase start publishes {name, index, total} to the live publisher."""
    import agentic_dynamics.runtime.workflow_runner as wr

    published = []

    class FakePublisher:
        def __init__(self, cell_id):
            self.cell_id = cell_id
            self.enabled = True

        def set_status(self, status):
            pass

        def set_phase(self, phase):
            published.append(phase)

        def publish_event(self, event):
            pass

    monkeypatch.setattr(wr, "LivePublisher", FakePublisher)
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)

    spec = load_spec(SPEC)
    run_workflow(spec, goal="g", model="m", workdir=tmp_path,
                 commit=False, run_agentic_fn=lambda *a, **k: _fake_agent())

    assert [p["name"] for p in published] == ["scope", "ux_design", "implement", "verify"]
    assert all(p["total"] == 4 for p in published)
    assert [p["index"] for p in published] == [1, 2, 3, 4]


def test_run_workflow_publishes_phase_before_agent_runs(tmp_path, monkeypatch):
    """The phase badge is set at phase *start*, before the agent is invoked."""
    import agentic_dynamics.runtime.workflow_runner as wr

    order = []

    class FakePublisher:
        def __init__(self, cell_id):
            self.enabled = True

        def set_status(self, status):
            pass

        def set_phase(self, phase):
            order.append(("phase", phase["name"]))

        def publish_event(self, event):
            pass

    monkeypatch.setattr(wr, "LivePublisher", FakePublisher)
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)

    spec = load_spec(SPEC)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        order.append(("agent",))
        return _fake_agent()

    run_workflow(spec, goal="g", model="m", workdir=tmp_path,
                 commit=False, run_agentic_fn=agent)

    # scope, ux_design, implement are agent phases (phase-before-agent); verify is
    # a test phase and emits a phase start with no agent invocation.
    assert order == [
        ("phase", "scope"), ("agent",),
        ("phase", "ux_design"), ("agent",),
        ("phase", "implement"), ("agent",),
        ("phase", "verify"),
    ]


def test_run_workflow_resume_publishes_original_phase_index(tmp_path, monkeypatch):
    """On resume, the badge keeps the 1-based absolute index, not a re-based one."""
    import agentic_dynamics.runtime.workflow_runner as wr

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    captured = []

    class FakePublisher:
        def __init__(self, cell_id):
            self.enabled = True

        def set_status(self, status):
            pass

        def set_phase(self, phase):
            captured.append(phase)

        def publish_event(self, event):
            pass

    monkeypatch.setattr(wr, "LivePublisher", FakePublisher)
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)

    spec = load_spec(SPEC)
    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(prompt)
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "x.md").write_text(str(len(calls)))  # unique -> commits
        return _fake_agent(ok=len(calls) < 3, error="boom")

    run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    # implement (3rd agent call) failed -> only scope + ux_design committed.

    captured.clear()
    calls.clear()

    def agent2(prompt, *, model, backend, workdir, **kwargs):
        calls.append(prompt)
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "x.md").write_text(str(len(calls)))
        return _fake_agent()

    run_workflow(spec, goal="g", model="m", workdir=tmp_path,
                 resume=True, run_agentic_fn=agent2)

    assert [p["name"] for p in captured] == ["implement", "verify"]
    assert [p["index"] for p in captured] == [3, 4]
    assert all(p["total"] == 4 for p in captured)


def test_run_workflow_fails_fast(tmp_path):
    spec = load_spec(SPEC)
    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(prompt)
        return _fake_agent(ok=False, error="boom") if len(calls) == 1 else _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path,
                          commit=False, run_agentic_fn=agent)
    assert len(result.phases) == 1  # stopped after first failure
    assert result.phases[0].status == "failed"
    assert result.phases[0].error == "boom"
    assert result.ok is False


def test_run_workflow_verify_phase_runs_tests(tmp_path):
    spec = load_spec(SPEC)
    (tmp_path / "test_ok.py").write_text("def test_passes():\n    assert True\n")

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path,
                          commit=False, run_agentic_fn=lambda *a, **k: _fake_agent())
    verify = result.phases[-1]
    assert verify.phase == "verify"
    assert verify.test_executed_success is True
    assert verify.tests_passed >= 1


def test_run_workflow_commits_per_phase(tmp_path):
    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("scope content")
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    assert result.phases[0].commit_hash  # scope phase produced a commit
    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True)
    assert "[workflow] scope" in log.stdout


def test_run_workflow_excludes_instrument_from_commit(tmp_path):
    """The runner's own ``.instrument/`` transcripts never enter history (item 5.1)."""
    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / ".instrument").mkdir(exist_ok=True)
        (Path(workdir) / ".instrument" / "session.jsonl").write_text("transcript")
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("scope")
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    assert result.phases[0].commit_hash
    tracked = subprocess.run(["git", "ls-files"], cwd=tmp_path, capture_output=True, text=True)
    assert ".instrument" not in tracked.stdout
    assert "docs/scope.md" in tracked.stdout


def test_run_workflow_resume_skips_committed_phases(tmp_path):
    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(prompt.splitlines()[1])
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "x.md").write_text(str(len(calls)))  # unique → commits
        return _fake_agent(ok=len(calls) < 3, error="boom")

    run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    # implement (3rd agent call) failed → only scope + ux committed

    calls.clear()

    def agent2(prompt, *, model, backend, workdir, **kwargs):
        calls.append(prompt.splitlines()[1])
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "x.md").write_text(str(len(calls)))
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path,
                          resume=True, run_agentic_fn=agent2)
    assert [p.phase for p in result.phases] == ["implement", "verify"]
    assert len(calls) == 1  # only implement re-runs; scope/ux skipped


# ── RAG augmentation seam ───────────────────────────────────────

class _FakeEvidence:
    def __init__(self, cid, text, authority="source"):
        self.id = cid
        self.text = text
        self.authority = authority
        self.content_hash = f"ch:{cid}"
        self.token_count = len(text.split())

    def citation(self):
        return f"[K:{self.id}@abc:loc]"


class _FakeAttempt:
    def __init__(self, evidence, fallback_mode="full"):
        self.selected_evidence = evidence
        self.fallback_mode = fallback_mode
        self.retrieval_attempt_id = "ra:test"


class _FakeAugmented:
    def __init__(self, prompt):
        self.prompt = prompt
        self.fallback = False
        self.evidence_ids = ["k1"]
        self.versions = {"schema": "prompt-plan/v1"}
        self.token_counts = {"in": 10}
        self.cost_usd = 0.0
        self.constructor_attempt_id = "ca:test"


def test_no_rag_default_is_byte_identical(tmp_path):
    spec = load_spec(SPEC)
    prompts = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        prompts.append(prompt)
        return _fake_agent()

    run_workflow(spec, goal="the goal", model="m", workdir=tmp_path,
                 commit=False, run_agentic_fn=agent)

    prior = []
    expected = []
    for p in spec.workflow.params["phases"]:
        if p.get("kind", "agent") == "agent":
            expected.append(_build_phase_prompt(p, "the goal", prior))
        prior.append(f"{p['name']} (ok)")
    assert prompts == expected


def test_rag_hook_ordering_between_route_and_agent(tmp_path):
    spec = load_spec(SPEC)
    order = []

    def retrieve_fn(**kwargs):
        order.append("retrieve")
        return _FakeAttempt([_FakeEvidence("k1", "cached evidence")])

    def construct_fn(request):
        order.append("construct")
        return _FakeAugmented("AUGMENTED: " + request.raw_work_item)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        order.append("agent")
        return _fake_agent()

    run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                 rag_augment=True, retrieve_fn=retrieve_fn, construct_fn=construct_fn,
                 run_agentic_fn=agent)

    # scope, ux_design, implement are agent phases (retrieve -> construct -> agent);
    # verify is a test phase and is bypassed entirely.
    assert order == ["retrieve", "construct", "agent"] * 3


def test_rag_bypasses_test_phases(tmp_path):
    spec = load_spec(SPEC)
    retrieve_calls = []

    def retrieve_fn(**kwargs):
        retrieve_calls.append(kwargs["raw_work_item"])
        return _FakeAttempt([_FakeEvidence("k1", "x")])

    def construct_fn(request):
        return _FakeAugmented("AUG")

    run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                 rag_augment=True, retrieve_fn=retrieve_fn, construct_fn=construct_fn,
                 run_agentic_fn=lambda *a, **k: _fake_agent())

    assert len(retrieve_calls) == 3  # verify (kind == test) is never augmented


def test_rag_prompt_is_augmented_and_provenance_serialized(tmp_path):
    spec = load_spec(SPEC)
    captured = []

    def retrieve_fn(**kwargs):
        return _FakeAttempt([_FakeEvidence("k1", "cached evidence")])

    def construct_fn(request):
        return _FakeAugmented("AUGMENTED: " + request.raw_work_item)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        captured.append(prompt)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                          rag_augment=True, retrieve_fn=retrieve_fn, construct_fn=construct_fn,
                          run_agentic_fn=agent)

    assert captured[0].startswith("AUGMENTED: ")
    d = result.phases[0].to_dict()
    assert d["raw_prompt_hash"]
    assert d["retrieval_attempt_id"] == "ra:test"
    assert d["constructor_attempt_id"] == "ca:test"
    assert d["selected_evidence_ids"] == ["k1"]
    assert d["fallback_mode"] == "full"
    assert "pre_phase_commit" in d
    assert "augmentation_versions" in d
    assert "augmentation_tokens" in d
    assert "augmentation_cost_usd" in d
    assert "augmentation_latency_ms" in d


def test_rag_fallback_on_retrieve_failure(tmp_path):
    spec = load_spec(SPEC)
    captured = []

    def retrieve_fn(**kwargs):
        raise RuntimeError("chroma down")

    def construct_fn(request):
        raise AssertionError("must not be called")

    def agent(prompt, *, model, backend, workdir, **kwargs):
        captured.append(prompt)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                          rag_augment=True, retrieve_fn=retrieve_fn, construct_fn=construct_fn,
                          run_agentic_fn=agent)

    assert result.phases[0].fallback_mode == "no_rag"
    assert result.phases[0].status == "ok"  # never blocked the phase
    expected = _build_phase_prompt(spec.workflow.params["phases"][0], "g", [])
    assert captured[0] == expected


def test_rag_fallback_on_construct_failure(tmp_path):
    spec = load_spec(SPEC)

    def retrieve_fn(**kwargs):
        return _FakeAttempt([_FakeEvidence("k1", "x")])

    def construct_fn(request):
        raise RuntimeError("constructor model down")

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                          rag_augment=True, retrieve_fn=retrieve_fn, construct_fn=construct_fn,
                          run_agentic_fn=lambda *a, **k: _fake_agent())

    assert result.phases[0].fallback_mode == "no_rag"
    assert result.phases[0].status == "ok"


def test_default_retrieve_fn_binds_dense_and_graph_stores(monkeypatch):
    """The default retrieval wiring builds both stores and binds them to ``retrieve``.

    ``default_retrieve_fn`` constructs ``ChromaStore`` with the dedicated
    ``knowledge_chunks_v1`` collection and ``Neo4jClient`` with its own defaults,
    then returns a ``functools.partial`` carrying both as keyword args.
    """
    import agentic_dynamics.knowledge.embeddings as embeddings
    import agentic_dynamics.knowledge.graph as graph

    constructed = {}

    class _FakeChroma:
        def __init__(self, **kwargs):
            constructed["chroma_kwargs"] = kwargs

    class _FakeNeo4j:
        def __init__(self, **kwargs):
            constructed["neo4j_kwargs"] = kwargs

    monkeypatch.setattr(embeddings, "ChromaStore", _FakeChroma)
    monkeypatch.setattr(graph, "Neo4jClient", _FakeNeo4j)

    fn = default_retrieve_fn()

    assert isinstance(fn.keywords["dense_store"], _FakeChroma)
    assert isinstance(fn.keywords["graph_client"], _FakeNeo4j)
    assert constructed["chroma_kwargs"]["collection_name"] == "knowledge_chunks_v1"
    assert constructed["neo4j_kwargs"] == {}


def test_default_retrieve_fn_degrades_to_no_rag_when_stores_down(tmp_path, monkeypatch):
    """A store that cannot connect degrades to ``no_rag`` without raising.

    Both store classes are swapped for fakes that construct fine but raise at query
    time (a lazy driver whose infra is down). ``retrieve``'s per-leg try/except marks
    each leg down, so the phase falls back to the base prompt and stays ``ok``.
    """
    import agentic_dynamics.knowledge.embeddings as embeddings
    import agentic_dynamics.knowledge.graph as graph

    class _DownChroma:
        def __init__(self, **kwargs):
            pass

        def search(self, *args, **kwargs):
            raise RuntimeError("chroma unreachable")

    class _DownNeo4j:
        def __init__(self, **kwargs):
            pass

        def search_knowledge_fulltext(self, *args, **kwargs):
            raise RuntimeError("neo4j unreachable")

    monkeypatch.setattr(embeddings, "ChromaStore", _DownChroma)
    monkeypatch.setattr(graph, "Neo4jClient", _DownNeo4j)

    spec = load_spec(SPEC)

    def construct_fn(request):
        return _FakeAugmented("AUGMENTED: " + request.raw_work_item)

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                          rag_augment=True, construct_fn=construct_fn,
                          run_agentic_fn=lambda *a, **k: _fake_agent())

    assert result.phases[0].fallback_mode == "no_rag"
    assert result.phases[0].status == "ok"


# ── Per-cell retrieval scope threading ──────────────────────────

def test_cell_scope_uses_worktree_basename(tmp_path, monkeypatch):
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    assert cell_scope(tmp_path) == f"self-{tmp_path.name}"


def test_cell_scope_overridden_by_finops_cell_id(tmp_path, monkeypatch):
    monkeypatch.setenv("FINOPS_CELL_ID", "wf_override")
    assert cell_scope(tmp_path) == "self-wf_override"


def test_rag_empty_repository_id_defaults_to_cell_scope(tmp_path, monkeypatch):
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    spec = load_spec(SPEC)
    captured = {}

    def retrieve_fn(**kwargs):
        captured["repository_id"] = kwargs.get("repository_id")
        captured["acl_scope"] = kwargs.get("acl_scope")
        return _FakeAttempt([_FakeEvidence("k1", "x")])

    run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                 rag_augment=True, retrieve_fn=retrieve_fn,
                 construct_fn=lambda request: _FakeAugmented("AUG"),
                 run_agentic_fn=lambda *a, **k: _fake_agent())

    # The empty scope resolves to the per-cell scope, not the global store.
    expected = f"self-{tmp_path.name}"
    assert captured["repository_id"] == expected
    assert captured["acl_scope"] == expected


def test_rag_explicit_repository_id_is_preserved(tmp_path, monkeypatch):
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    spec = load_spec(SPEC)
    captured = {}

    def retrieve_fn(**kwargs):
        captured["repository_id"] = kwargs.get("repository_id")
        captured["acl_scope"] = kwargs.get("acl_scope")
        return _FakeAttempt([_FakeEvidence("k1", "x")])

    run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                 rag_augment=True, rag_params={"repository_id": "shared-scope"},
                 retrieve_fn=retrieve_fn,
                 construct_fn=lambda request: _FakeAugmented("AUG"),
                 run_agentic_fn=lambda *a, **k: _fake_agent())

    # The shared-scope override is preserved unchanged — never overwritten by the
    # per-cell default.
    assert captured["repository_id"] == "shared-scope"


def test_retrieve_construct_render_path_never_writes():
    """The augmentation seam is read-only; the sole KB writer is the opt-in emit_self path.

    ``retrieve -> construct -> render`` must reference ``publish_event`` ZERO times — the
    seam reads (dense + lexical retrieval) and constructs (one flash-model call), but it can
    never write the knowledge plane. The only write is the self-build producer
    (``emit_phase_finding``), reached exclusively through ``_emit_self_finding`` (gated by
    ``rag_params.emit_self``).
    """
    import inspect

    import agentic_dynamics.knowledge.augment as augment
    import agentic_dynamics.knowledge.prompt_constructor as pc
    import agentic_dynamics.knowledge.retrieval as retrieval_mod
    from agentic_dynamics.runtime import workflow_runner as wr

    # The two read-side modules never reference publish_event.
    for mod in (retrieval_mod, pc):
        assert "publish_event" not in inspect.getsource(mod)

    # The seam's retrieve/construct/render functions never reference publish_event either.
    for fn in (augment.augment_prompt, augment.default_retrieve_fn, augment.default_construct_fn):
        assert "publish_event" not in inspect.getsource(fn)

    # The write is funneled through emit_phase_finding (not publish_event) and lives only in
    # the emit_self helper — so an augmented phase can never write except through emit_self.
    assert "emit_phase_finding" in inspect.getsource(wr._emit_self_finding)
    assert "publish_event" not in inspect.getsource(wr._emit_self_finding)


# ── spec_id on the ledger records ───────────────────────────────


def test_ledger_records_carry_spec_id(tmp_path):
    """``spec_id`` is a declared LEDGER_FIELD; job *and* attempt records must emit it.

    Without it a run ledger identifies only the spec *name*, so two runs across a version
    bump are indistinguishable in the ledger.
    """
    spec = load_spec(SPEC)
    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path,
                          commit=False, run_agentic_fn=lambda *a, **k: _fake_agent())

    expected = f"{spec.name}@{spec.version}"
    assert result.spec_id == expected                                  # job record
    assert all(p.spec_id == expected for p in result.phases)           # attempt records

    serialized = result.to_dict()
    assert serialized["spec_id"] == expected
    assert all(ph["spec_id"] == expected for ph in serialized["phases"])


# ── --resume: git log first, the derived index as the fallback ──


def _index_ledger(tmp_path: Path, goal: str, phases: list[dict]) -> SpecStatusEntry:
    """Write a fixture run ledger under ``tmp_path`` and return an entry pointing at it."""
    rel = "experiments/results/workflows/control_room_portal/20260819T000000Z.json"
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"spec_name": "control_room_portal", "goal": goal, "phases": phases})
    )
    return SpecStatusEntry(
        name="control_room_portal", version="0.2", status="active",
        spec_path="experiments/specs/control_room_portal.yaml",
        last_run_at="2026-08-19T00:00:00+00:00", results_pointer=rel, n_runs=1,
    )


def test_resume_falls_back_to_the_index_without_workflow_commits(tmp_path, monkeypatch):
    # tmp_path is not a git repo, so the git-log path finds nothing — exactly the case
    # the index fallback exists for.
    entry = _index_ledger(tmp_path, "g", [
        {"phase": "scope", "status": "ok"},
        {"phase": "ux_design", "status": "ok"},
        {"phase": "implement", "status": "failed"},
    ])
    monkeypatch.setattr(workflow_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(spec_status, "index_entry", lambda name, **kw: entry)

    spec = load_spec(SPEC)
    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, resume=True,
                          commit=False, run_agentic_fn=lambda *a, **k: _fake_agent())
    # scope/ux_design were ok in the ledger and are skipped; the failed implement re-runs.
    assert [p.phase for p in result.phases] == ["implement", "verify"]


def test_index_fallback_is_not_consulted_when_commits_exist(tmp_path, monkeypatch):
    """The git-log path stays primary — the pre-existing behaviour must not regress."""
    consulted = []
    monkeypatch.setattr(
        spec_status, "index_entry", lambda name, **kw: consulted.append(name)
    )
    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(prompt)
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "x.md").write_text(str(len(calls)))
        return _fake_agent(ok=len(calls) < 2, error="boom")

    run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, resume=True,
                          run_agentic_fn=lambda *a, **k: _fake_agent())
    assert [p.phase for p in result.phases][0] == "ux_design"  # scope skipped via git log
    assert consulted == []                                     # ... and the index untouched


def test_index_fallback_requires_a_matching_goal(tmp_path, monkeypatch):
    # Phase names collide across workflows (scope/verify), so a ledger written for a
    # different goal must not let a resume skip work that was never done for this one.
    entry = _index_ledger(tmp_path, "a completely different goal",
                          [{"phase": "scope", "status": "ok"}])
    monkeypatch.setattr(workflow_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(spec_status, "index_entry", lambda name, **kw: entry)

    spec = load_spec(SPEC)
    phase_names = [p["name"] for p in spec.workflow.params["phases"]]
    assert _completed_phases_from_index(spec, phase_names, "g") == set()


def test_index_fallback_degrades_to_empty_on_any_failure(tmp_path, monkeypatch):
    """No index, a dangling results_pointer, or a raising lookup all mean "start over"."""
    spec = load_spec(SPEC)
    phase_names = [p["name"] for p in spec.workflow.params["phases"]]
    monkeypatch.setattr(workflow_runner, "PROJECT_ROOT", tmp_path)

    monkeypatch.setattr(spec_status, "index_entry", lambda name, **kw: None)
    assert _completed_phases_from_index(spec, phase_names, "g") == set()

    dangling = SpecStatusEntry(name="control_room_portal", version="0.2", status="active",
                               spec_path="x.yaml", results_pointer="does/not/exist.json")
    monkeypatch.setattr(spec_status, "index_entry", lambda name, **kw: dangling)
    assert _completed_phases_from_index(spec, phase_names, "g") == set()

    def boom(name, **kw):
        raise RuntimeError("index exploded")

    monkeypatch.setattr(spec_status, "index_entry", boom)
    assert _completed_phases_from_index(spec, phase_names, "g") == set()
