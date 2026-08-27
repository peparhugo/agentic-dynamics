"""Tests for the execute runner — run_workflow drives agent_task phases in a worktree."""

import json
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from agentic_dynamics.experiment import spec_status
from agentic_dynamics.experiment.experiment_spec import load_spec, validate_spec
from agentic_dynamics.experiment.spec_status import SpecStatusEntry
from agentic_dynamics.knowledge.augment import default_retrieve_fn
from agentic_dynamics.runtime import workflow_runner
from agentic_dynamics.runtime.workflow_runner import (
    _build_phase_prompt,
    _completed_phases_from_index,
    cell_scope,
    run_workflow,
)

SPEC = Path(__file__).resolve().parent.parent / "workflows" / "repository" / "control_room_portal.yaml"


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

    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)

    spec = load_spec(SPEC)
    run_workflow(spec, goal="g", model="m", workdir=tmp_path,
                 commit=False, run_agentic_fn=lambda *a, **k: _fake_agent(),
                 publisher_factory=FakePublisher)

    assert [p["name"] for p in published] == ["scope", "ux_design", "implement", "verify"]
    assert all(p["total"] == 4 for p in published)
    assert [p["index"] for p in published] == [1, 2, 3, 4]


def test_run_workflow_publishes_phase_before_agent_runs(tmp_path, monkeypatch):
    """The phase badge is set at phase *start*, before the agent is invoked."""
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

    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)

    spec = load_spec(SPEC)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        order.append(("agent",))
        return _fake_agent()

    run_workflow(spec, goal="g", model="m", workdir=tmp_path,
                 commit=False, run_agentic_fn=agent, publisher_factory=FakePublisher)

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

    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)

    spec = load_spec(SPEC)
    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(prompt)
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "x.md").write_text(str(len(calls)))  # unique -> commits
        return _fake_agent(ok=len(calls) < 3, error="boom")

    run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent,
                 publisher_factory=FakePublisher)
    # implement (3rd agent call) failed -> only scope + ux_design committed.

    captured.clear()
    calls.clear()

    def agent2(prompt, *, model, backend, workdir, **kwargs):
        calls.append(prompt)
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "x.md").write_text(str(len(calls)))
        return _fake_agent()

    run_workflow(spec, goal="g", model="m", workdir=tmp_path,
                 resume=True, run_agentic_fn=agent2, publisher_factory=FakePublisher)

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


def test_run_workflow_change_analysis_seam(tmp_path, monkeypatch):
    """Review F3: an injected ChangeAnalyzer runs over each committed phase, best-effort,
    and the analysis lands on the phase result — the seam is inert without injection."""
    from agentic_dynamics.runtime.change_analyzer import ChangeAnalysis

    # The sonar/lsp legs are covered by their own unit tests; here they are stubbed to their
    # measured unavailable status so the seam test never reaches the real scanner/mypy.
    monkeypatch.setattr(workflow_runner, "_sonar_evidence",
                        lambda *a, **k: {"status": "unavailable", "revision_matches": None,
                                         "new_critical_count": None, "analyzed_sha": ""})
    monkeypatch.setattr(workflow_runner, "_lsp_evidence",
                        lambda *a, **k: {"status": "unavailable", "new_error_count": None,
                                         "tool": "mypy"})

    class RecordingAnalyzer:
        def __init__(self):
            self.changes = []

        def analyze(self, change):
            self.changes.append(change)
            return ChangeAnalysis(
                facts=({"predicate": "changed_symbol_count", "value": "1",
                        "value_type": "int", "evidence_ids": ()},),
                neighborhood=("f",),
            )

    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        n = len(calls)
        calls.append(n)
        (Path(workdir) / "app.py").write_text(f"def f{n}():\n    return {n}\n")
        return _fake_agent(files_created=["app.py"])

    analyzer = RecordingAnalyzer()
    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path,
                          run_agentic_fn=agent, change_analyzer=analyzer)

    # The FIRST phase's commit is the worktree's root commit — no parent to diff, so the
    # seam degrades to None. The SECOND committed phase has a parent: it gets analyzed.
    assert result.phases[0].commit_hash
    assert result.phases[0].change_analysis is None  # root commit: no parent to diff
    assert result.phases[1].commit_hash
    assert analyzer.changes  # the analyzer saw the second phase's change
    change = analyzer.changes[0]
    assert change.delta is not None
    assert {s.qualified_name for s in change.delta.added_symbols} == {"f1"}
    assert {s.qualified_name for s in change.delta.removed_symbols} == {"f0"}
    assert result.phases[1].change_analysis["neighborhood"] == ["f"]
    assert result.phases[1].change_analysis["facts"][0]["predicate"] == "changed_symbol_count"
    assert result.phases[1].change_analysis["graph_updated"] is False


def test_run_workflow_change_analysis_inert_without_injection(tmp_path):
    """Without an injected analyzer the seam is inert: change_analysis stays None, the phase
    result is byte-identical to a plain run (review F3's no-op default), and NO evidence block
    reaches any phase prompt."""
    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    prompts = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        prompts.append(prompt)
        (Path(workdir) / "app.py").write_text("def f():\n    return 1\n")
        return _fake_agent(files_created=["app.py"])

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    assert result.phases[0].commit_hash
    assert result.phases[0].change_analysis is None
    assert all(p.change_analysis is None for p in result.phases)
    assert all("EVIDENCE" not in p for p in prompts)  # prompts byte-identical without injection


def test_run_workflow_change_analysis_full_sha_and_next_phase_evidence(tmp_path, monkeypatch):
    """cap_2a p1 (design §5.7): the ChangeInput revisions are FULL commit SHAs (provenance,
    the short hash stays display-only), and the NEXT phase's prompt receives a bounded,
    machine-readable evidence context (graph status, full revision, neighborhood, facts)."""
    import re

    from agentic_dynamics.runtime.change_analyzer import ChangeAnalysis

    monkeypatch.setattr(workflow_runner, "_sonar_evidence",
                        lambda *a, **k: {"status": "unavailable", "revision_matches": None,
                                         "new_critical_count": None, "analyzed_sha": ""})
    monkeypatch.setattr(workflow_runner, "_lsp_evidence",
                        lambda *a, **k: {"status": "unavailable", "new_error_count": None,
                                         "tool": "mypy"})

    class RecordingAnalyzer:
        def __init__(self):
            self.changes = []

        def analyze(self, change):
            self.changes.append(change)
            return ChangeAnalysis(
                facts=({"predicate": "changed_symbol_count", "value": "1",
                        "value_type": "int", "evidence_ids": ()},),
                neighborhood=("f",),
                graph_status="available",
                revision=change.revision,
            )

    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    prompts = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        prompts.append(prompt)
        n = len(prompts)
        (Path(workdir) / "app.py").write_text(f"def f{n}():\n    return {n}\n")
        return _fake_agent(files_created=["app.py"])

    analyzer = RecordingAnalyzer()
    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path,
                          run_agentic_fn=agent, change_analyzer=analyzer)

    # The FIRST phase's commit is the root commit (no parent to diff) -> not analyzed; the
    # SECOND committed phase is analyzed with FULL-SHA revisions.
    assert result.phases[0].change_analysis is None
    assert len(analyzer.changes) >= 1
    change = analyzer.changes[0]
    assert re.fullmatch(r"[0-9a-f]{40}", change.revision) is not None  # full SHA, not short
    assert change.after.revision == change.revision
    assert re.fullmatch(r"[0-9a-f]{40}", change.before.revision) is not None  # parent full SHA
    # The displayed commit_hash stays the SHORT form.
    assert re.fullmatch(r"[0-9a-f]{7,}", result.phases[1].commit_hash) is not None
    assert len(result.phases[1].commit_hash) < len(change.revision)

    # The NEXT agent phase's prompt (implement, after ux_design was analyzed) carries the
    # bounded evidence block with graph status, revision, neighborhood, and facts.
    evidence_prompts = [p for p in prompts if "EVIDENCE" in p]
    assert evidence_prompts, "the next-phase prompt must receive the evidence context"
    line = next(ln for ln in evidence_prompts[0].splitlines() if ln.strip().startswith("- EVIDENCE"))
    payload = json.loads(line.split("EVIDENCE ", 1)[1])
    assert payload["graph_status"] == "available"
    assert payload["revision"] == change.revision
    assert payload["neighborhood"] == ["f"]
    assert payload["facts"][0]["predicate"] == "changed_symbol_count"
    assert payload["phase"] == "ux_design"  # the analyzed phase whose evidence rode forward


def test_run_workflow_change_analysis_root_commit_never_fails(tmp_path):
    """A phase whose commit has NO parent (root commit in the worktree) cannot be diffed —
    the seam degrades to None instead of failing the phase."""
    from agentic_dynamics.runtime.change_analyzer import ChangeAnalysis

    class Analyzer:
        def analyze(self, change):
            return ChangeAnalysis()

    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    # Commit the FIRST phase's change directly (no parent), then let the runner commit a
    # second phase whose analysis targets commit^ — the runner's own first commit is root.
    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "app.py").write_text("def f():\n    return 1\n")
        return _fake_agent(files_created=["app.py"])

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path,
                          run_agentic_fn=agent, change_analyzer=Analyzer())
    assert result.ok
    # Root-commit phases degrade gracefully (change_analysis may be None), never a failure.
    assert all(p.status == "ok" for p in result.phases)


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
        name="control_room_portal", version="0.2", status="runnable",
        spec_path="workflows/repository/control_room_portal.yaml",
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

    dangling = SpecStatusEntry(name="control_room_portal", version="0.2", status="runnable",
                               spec_path="x.yaml", results_pointer="does/not/exist.json")
    monkeypatch.setattr(spec_status, "index_entry", lambda name, **kw: dangling)
    assert _completed_phases_from_index(spec, phase_names, "g") == set()

    def boom(name, **kw):
        raise RuntimeError("index exploded")

    monkeypatch.setattr(spec_status, "index_entry", boom)
    assert _completed_phases_from_index(spec, phase_names, "g") == set()


# ── v2 analyzer legs: severity filter + novelty + deadline (cap_2a rerun2 p1) ──


def _avail_metrics():
    from agentic_dynamics.measurement.sonar import SONAR_STATUS_AVAILABLE, SonarMetrics

    return SonarMetrics(project_key="exp_wt", analyzed=True, status=SONAR_STATUS_AVAILABLE,
                        analyzed_sha="c" * 40)


def _issue(rule, severity, file_path, line):
    from agentic_dynamics.measurement.sonar import SonarIssue

    return SonarIssue(rule=rule, severity=severity, file_path=file_path, line=line)


def test_call_with_deadline_returns_false_on_timeout():
    """(c) A non-returning analyzer leg is bounded by the client-side deadline — it degrades to
    ``(False, None)`` instead of hanging the phase."""
    import time

    from agentic_dynamics.runtime import workflow_runner as wr

    def slow():
        time.sleep(1.0)
        return "never"

    returned, result = wr._call_with_deadline(slow, timeout=0.05)
    assert returned is False
    assert result is None


def test_sonar_evidence_no_parent_checkout_is_unavailable(tmp_path):
    """A failed parent materialization degrades the sonar leg to its measured unavailable
    status (count omitted — null-not-zero, never a fabricated 0)."""
    from agentic_dynamics.runtime import workflow_runner as wr

    payload = wr._sonar_evidence(tmp_path, None, "0" * 40, "1" * 40)
    assert payload["status"] == "unavailable"
    assert payload["new_critical_count"] is None


def test_sonar_evidence_novelty_introduced_blocker_counts_one(monkeypatch, tmp_path):
    """(b) Novelty rule: a change-introduced BLOCKER (present only in the after-analysis) counts
    exactly 1, and the leg requests the server-side BLOCKER,CRITICAL severity filter."""
    from agentic_dynamics.runtime import workflow_runner as wr

    monkeypatch.setattr(wr, "run_sonar_analysis", lambda *a, **k: _avail_metrics())
    seen = {}

    def fake_fetch(key, severities="", ps=500):
        seen["severities"] = severities
        if key.endswith("0" * 12):  # the parent revision: no criticals
            return []
        return [_issue("python:S1000", "BLOCKER", "calc.py", 10)]

    monkeypatch.setattr(wr, "fetch_sonar_issues", fake_fetch)
    payload = wr._sonar_evidence(tmp_path, tmp_path, "0" * 40, "1" * 40)
    assert payload["status"] == "available"
    assert payload["new_critical_count"] == 1
    assert seen["severities"] == "BLOCKER,CRITICAL"


def test_sonar_evidence_preexisting_blocker_counts_zero(monkeypatch, tmp_path):
    """(b) Novelty rule: a pre-existing BLOCKER (same identity in BOTH revisions, untouched by
    the change) counts 0."""
    from agentic_dynamics.runtime import workflow_runner as wr

    monkeypatch.setattr(wr, "run_sonar_analysis", lambda *a, **k: _avail_metrics())
    blocker = _issue("python:S1000", "BLOCKER", "calc.py", 5)
    monkeypatch.setattr(wr, "fetch_sonar_issues", lambda key, severities="", ps=500: [blocker])

    payload = wr._sonar_evidence(tmp_path, tmp_path, "0" * 40, "1" * 40)
    assert payload["status"] == "available"
    assert payload["new_critical_count"] == 0


def test_lsp_evidence_novelty_introduced_error_counts_one(monkeypatch, tmp_path):
    """The LSP leg counts only change-introduced ERROR diagnostics by (file, line, code)."""
    from agentic_dynamics.measurement.lsp_diagnostics import LSPDiagnostic, LSPReport
    from agentic_dynamics.runtime import workflow_runner as wr

    calls = []

    def fake_diag(path, profile, tool_name=None):
        n = len(calls)
        calls.append(path)
        if n == 0:  # parent revision: clean
            return LSPReport(tool="mypy", language="python", available=True)
        return LSPReport(
            tool="mypy", language="python", available=True,
            diagnostics=[LSPDiagnostic("error", "bad", "calc.py", 10, 5, "return-value")],
        )

    monkeypatch.setattr(wr, "run_diagnostics", fake_diag)
    payload = wr._lsp_evidence(tmp_path, tmp_path, "0" * 40, "1" * 40, None)
    assert payload["status"] == "available"
    assert payload["new_error_count"] == 1
    assert payload["tool"] == "mypy"


# ── Phase watchdog (cap_runner_hardening p1) ─────────────────────


def _watchdog_transcript(workdir):
    return Path(workdir) / ".instrument" / "session.jsonl"


def _watchdog_stalled_agent(killed, release):
    """A fake agent that writes one step, registers a SIGTERM-recording kill, then goes quiet.

    The watchdog must SIGTERM it (recording the kill) and fail the phase with STALLED while
    the agent itself keeps waiting until the kill releases it.
    """

    def agent(prompt, *, model, backend, workdir, watchdog=None, **kwargs):
        transcript = _watchdog_transcript(workdir)
        transcript.parent.mkdir(parents=True, exist_ok=True)
        watchdog["kill"] = lambda: (killed.append("SIGTERM"), release.set())
        with transcript.open("a") as fh:
            fh.write(json.dumps({"type": "step_start"}) + "\n")
        release.wait(timeout=5)  # no further steps — the transcript goes stale past the threshold
        return _fake_agent()

    return agent


def test_watchdog_sigterms_a_stalled_agent_and_fails_the_phase(tmp_path):
    """(a) A fake agent that stops writing steps for > threshold is SIGTERM'd and the phase
    fails with STALLED + evidence (last-step timestamp, stale age, transcript tail), and the
    evidence rides the phase's ledger record."""
    spec = load_spec(SPEC)
    killed: list[str] = []
    release = threading.Event()

    result = run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, commit=False,
        phase_watchdog_min=0.03,  # 1.8s — the test's whole runtime budget
        run_agentic_fn=_watchdog_stalled_agent(killed, release),
    )
    p = result.phases[0]
    assert p.status == "failed"
    assert p.stall_evidence is not None
    assert p.stall_evidence["reason"] == "STALLED"
    assert p.stall_evidence["stale_age_s"] >= p.stall_evidence["threshold_min"] * 60
    assert p.stall_evidence["last_step_at"]
    assert "step_start" in p.stall_evidence["transcript_tail"]
    assert "STALLED" in p.error
    assert killed == ["SIGTERM"]  # the watchdog actually killed the agent
    assert result.ok is False

    # The ledger carries the evidence, not just the error string.
    ledger = result.to_dict()["phases"][0]
    assert ledger["stall_evidence"]["reason"] == "STALLED"
    assert ledger["status"] == "failed"


def test_watchdog_never_kills_a_compliant_agent(tmp_path):
    """(b) A fake agent that keeps stepping — even slowly — is never killed; the phase stays ok."""
    spec = load_spec(SPEC)
    killed: list[str] = []
    release = threading.Event()

    def agent(prompt, *, model, backend, workdir, watchdog=None, **kwargs):
        transcript = _watchdog_transcript(workdir)
        transcript.parent.mkdir(parents=True, exist_ok=True)
        watchdog["kill"] = lambda: (killed.append("SIGTERM"), release.set())
        for i in range(5):
            with transcript.open("a") as fh:
                fh.write(json.dumps({"type": "step_start", "n": i}) + "\n")
            release.wait(timeout=0.3)  # continuous slow steps: max gap 0.3s < 1.8s threshold
        return _fake_agent()

    result = run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, commit=False,
        phase_watchdog_min=0.03, run_agentic_fn=agent,
    )
    assert result.phases[0].status == "ok"
    assert result.phases[0].stall_evidence is None
    assert killed == []


def test_watchdog_threshold_env_override(tmp_path, monkeypatch):
    """(c) FINOPS_PHASE_WATCHDOG_MIN overrides the default threshold; the stall fires under it."""
    monkeypatch.setenv("FINOPS_PHASE_WATCHDOG_MIN", "0.03")
    spec = load_spec(SPEC)
    killed: list[str] = []
    release = threading.Event()

    result = run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, commit=False,  # no explicit arg → env wins
        run_agentic_fn=_watchdog_stalled_agent(killed, release),
    )
    assert result.phases[0].status == "failed"
    assert result.phases[0].stall_evidence["reason"] == "STALLED"
    assert result.phases[0].stall_evidence["threshold_min"] == 0.03


def test_watchdog_explicit_arg_overrides_env(tmp_path, monkeypatch):
    """The CLI/arg threshold outranks the env: a huge explicit value means no stall even with a
    hostile small env value, and the kill never fires."""
    monkeypatch.setenv("FINOPS_PHASE_WATCHDOG_MIN", "0.03")  # would stall under the env alone
    spec = load_spec(SPEC)
    killed: list[str] = []
    release = threading.Event()

    def agent(prompt, *, model, backend, workdir, watchdog=None, **kwargs):
        transcript = _watchdog_transcript(workdir)
        transcript.parent.mkdir(parents=True, exist_ok=True)
        watchdog["kill"] = lambda: (killed.append("SIGTERM"), release.set())
        with transcript.open("a") as fh:
            fh.write("step\n")
        release.wait(timeout=0.8)  # short — the explicit 60-min threshold never fires here
        return _fake_agent()

    result = run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, commit=False,
        phase_watchdog_min=60.0, run_agentic_fn=agent,
    )
    assert result.phases[0].status == "ok"
    assert result.phases[0].stall_evidence is None
    assert killed == []


def test_watchdog_default_threshold_does_not_fire_for_a_quick_agent(tmp_path, monkeypatch):
    """The default (20 min) watchdog is inert for a normal quick agent — no stall, no overhead
    observable in the outcome."""
    monkeypatch.delenv("FINOPS_PHASE_WATCHDOG_MIN", raising=False)
    spec = load_spec(SPEC)
    result = run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, commit=False,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )
    assert result.ok
    assert all(p.stall_evidence is None for p in result.phases)


def test_watchdog_zero_disables_it(tmp_path, monkeypatch):
    """A threshold <= 0 turns the watchdog off — the phase is byte-identical to pre-hardening
    (no seam, no kill path, no stall possible)."""
    monkeypatch.setenv("FINOPS_PHASE_WATCHDOG_MIN", "0.03")
    spec = load_spec(SPEC)
    seen = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        seen.append(kwargs)
        time.sleep(1.0)  # would definitely stall under the env threshold — but it is disabled
        return _fake_agent()

    result = run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, commit=False,
        phase_watchdog_min=0, run_agentic_fn=agent,
    )
    assert result.phases[0].status == "ok"
    assert all("watchdog" not in kw for kw in seen)  # no seam threaded to the agent


def test_watchdog_only_wraps_agent_phases(tmp_path):
    """The watchdog wraps the agent process only — test phases run in-process (run_suite) and
    are never given a watchdog seam or a kill path."""
    spec = load_spec(SPEC)
    watchdogs = []

    def agent(prompt, *, model, backend, workdir, watchdog=None, **kwargs):
        watchdogs.append(watchdog)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                          run_agentic_fn=agent)
    # scope/ux_design/implement are agent phases → seam present; verify (kind=test) never calls agent.
    assert len(watchdogs) == 3
    assert all(w is not None for w in watchdogs)
    assert result.phases[-1].kind == "test"
    assert result.phases[-1].stall_evidence is None


# ── Deploy gate (cap_runner_hardening p2) ───────────────────────

#: Faithful reconstruction of the revamp2 p3 session's deploy event (the bash tool_use whose
#: input deployed BOTH production hosts). The command is the one that silently overwrote the
#: site twice — the replay proof the gate must catch.
REVAMP2_DEPLOY_LINE = json.dumps({
    "type": "tool_use",
    "timestamp": 1787783173755,
    "sessionID": "ses_fbfd53722ffeHBFPqC3B3fC6Se",
    "part": {
        "type": "tool",
        "tool": "bash",
        "callID": "call_revamp2_p3",
        "state": {
            "status": "completed",
            "input": {
                "command": "firebase deploy --only hosting && firebase deploy --only hosting --project agentic-dynamics",
                "workdir": "/tmp/wt_site_revamp2/apps/website",
                "timeout": 120000,
            },
            "output": "=== Deploying to 'ai-finops-rulebook'...\n\u2714 Deploy complete!\n"
                      "=== Deploying to 'agentic-dynamics'...\n\u2714 Deploy complete!\n",
        },
    },
})


def _deploy_agent(transcript_line, *, deploy_in_all=False):
    """A fake agent that writes ``transcript_line`` into the phase's session transcript, then
    succeeds. Models the real adapter's per-phase end-write: each phase REPLACES the transcript
    (``write_text``), so a later clean phase never inherits an earlier phase's deploy line."""
    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        n = len(calls)
        calls.append(n)
        transcript = _watchdog_transcript(workdir)
        transcript.parent.mkdir(parents=True, exist_ok=True)
        if deploy_in_all or n == 0:
            transcript.write_text(transcript_line + "\n")
        else:
            transcript.write_text('{"type": "step_start"}\n')
        return _fake_agent()

    return agent


def test_deploy_gate_fails_a_non_deploy_phase_with_evidence(tmp_path):
    """(a) A fake agent session containing 'firebase deploy' in a non-deploy phase fails with
    DEPLOY_GATE + the quoted offending command, and the evidence rides the phase's ledger record."""
    spec = load_spec(SPEC)
    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                          run_agentic_fn=_deploy_agent(REVAMP2_DEPLOY_LINE))
    p = result.phases[0]
    assert p.status == "failed"
    assert p.deploy_gate is not None
    assert p.deploy_gate["reason"] == "DEPLOY_GATE"
    assert any("firebase deploy" in v["command"] for v in p.deploy_gate["violations"])
    assert any("--project agentic-dynamics" in v["command"] for v in p.deploy_gate["violations"])
    assert p.deploy_gate["violations"][0]["line"].startswith("{")
    assert "DEPLOY_GATE" in p.error
    assert "'firebase deploy --only hosting" in p.error  # the offending command is quoted
    assert result.ok is False
    assert result.to_dict()["phases"][0]["deploy_gate"]["reason"] == "DEPLOY_GATE"


def test_deploy_gate_passes_a_deploy_allowed_phase(tmp_path):
    """(b) The same deploy command in a phase marked ``deploy_allowed: true`` passes — the gate
    is about the marker, never a naming rule; later clean phases stay clean (per-phase transcript)."""
    spec = load_spec(SPEC)
    spec.workflow.params["phases"][0]["deploy_allowed"] = True  # scope may deploy
    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                          run_agentic_fn=_deploy_agent(REVAMP2_DEPLOY_LINE))
    assert result.ok
    assert result.phases[0].status == "ok"
    assert result.phases[0].deploy_gate is None
    assert all(p.deploy_gate is None for p in result.phases)


def test_deploy_gate_not_triggered_by_clean_phases_or_test_phases(tmp_path):
    """A clean agent phase (no deploy command) and the test phase never trip the gate; a bash
    command that merely mentions firebase in text (not a deploy) is not a violation."""
    spec = load_spec(SPEC)
    clean_line = json.dumps({
        "type": "tool_use", "sessionID": "s",
        "part": {"type": "tool", "tool": "bash",
                 "state": {"input": {"command": "python scripts/build_data.py"}}},
    })

    def agent(prompt, *, model, backend, workdir, **kwargs):
        _watchdog_transcript(workdir).parent.mkdir(parents=True, exist_ok=True)
        _watchdog_transcript(workdir).write_text(clean_line + "\n")
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                          run_agentic_fn=agent)
    assert result.ok
    assert all(p.deploy_gate is None for p in result.phases)
    assert result.phases[-1].kind == "test"
    assert result.phases[-1].deploy_gate is None


def test_deploy_allowed_marker_is_type_checked(tmp_path):
    """(c) The validator type-checks the marker: a non-boolean (the typo that would silently
    disable the gate) is refused; a real boolean validates; specs without the marker (the whole
    committed corpus) validate unchanged."""
    spec = load_spec(SPEC)
    assert validate_spec(spec) == []  # the existing spec has no marker — still valid

    spec.workflow.params["phases"][0]["deploy_allowed"] = "true"  # string typo
    errors = validate_spec(spec)
    assert any("deploy_allowed must be a boolean" in e for e in errors)

    spec.workflow.params["phases"][0]["deploy_allowed"] = 1  # int typo
    errors = validate_spec(spec)
    assert any("deploy_allowed must be a boolean" in e for e in errors)

    spec.workflow.params["phases"][0]["deploy_allowed"] = True  # honest marker
    assert validate_spec(spec) == []


def test_deploy_gate_replay_revamp2_p3_session(tmp_path):
    """(d) Replay proof: the revamp2 p3 deploy command (the one that overwrote production) is
    caught by the gate — against the embedded transcript event AND, when the real worktree still
    exists on disk, against the actual /tmp/wt_site_revamp2 session transcript."""
    from agentic_dynamics.runtime import workflow_runner as wr

    # (1) the embedded reconstruction of the exact production-affecting command
    spec = load_spec(SPEC)
    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                          run_agentic_fn=_deploy_agent(REVAMP2_DEPLOY_LINE))
    p = result.phases[0]
    assert p.status == "failed"
    assert p.deploy_gate["reason"] == "DEPLOY_GATE"
    assert p.deploy_gate["violations"][0]["command"] == (
        "firebase deploy --only hosting && firebase deploy --only hosting --project agentic-dynamics"
    )
    assert p.deploy_gate["violations"][0]["pattern"] == "firebase deploy"

    # (2) against the real revamp2 session transcript when it is still on disk — the gate would
    # have fired on the exact line the evidence measured
    real = Path("/tmp/wt_site_revamp2/.instrument/session.jsonl")
    if real.exists():
        hits = wr._scan_transcript_for_deploys(real)
        assert any("firebase deploy" in h["command"] for h in hits), (
            "the real revamp2 p3 session must be caught by the deploy gate"
        )


# ── Commit-prefix enforcement (cap_runner_hardening p3) ──────────

#: The revamp2 branch's 7 plain-message commits (feature/site-revamp2, between the phase's
#: own [workflow] commit and the pre-phase spec commit) — the exact commits that broke the
#: resume machinery and forced the re-tagging surgery. The replay proof the validator must
#: reject.
REVAMP2_GOAL = "Deliver the site's IMPLEMENTED visual system"
REVAMP2_PLAIN_COMMITS = [
    "research: cap_site_revamp editorial audit",
    "site: add editorial visual system",
    "site: rewrite public research narrative",
    "site: wire campaign evidence to data",
    "site: harden evidence publication",
    "data: refresh site publication receipt",
    "docs: record site deploy verification",
]


def _git_init(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)


def test_commit_prefix_canonicalizes_a_plain_message_commit(tmp_path):
    """(a) A fake agent that commits a plain message: the default CANONICALIZE mode amends
    the message to the canonical pattern (the work preserved), records the original subject
    on the gate, and the phase CONTINUES — resume reliability is preserved because the
    message becomes canonical."""
    spec = load_spec(SPEC)
    _git_init(tmp_path)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("scope")
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "site: add things"], cwd=workdir, check=True)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "ok"  # canonicalized, not failed
    assert p.commit_gate is not None
    assert p.commit_gate["reason"] == "COMMIT_PREFIX_CANONICALIZED"
    assert p.commit_gate["original_subjects"] == ["site: add things"]
    assert p.commit_gate["expected_prefix"] == "[workflow] scope — g"
    # the message on disk IS canonical now — resume will match it
    subjects = subprocess.run(
        ["git", "log", "--format=%s"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.splitlines()
    assert subjects[0] == "[workflow] scope — g"


def test_commit_prefix_strict_mode_fails_a_plain_message_commit(tmp_path, monkeypatch):
    """FINOPS_COMMIT_GATE=strict restores the fail-with-evidence mode: a plain-message
    commit fails the phase with COMMIT_PREFIX + the subject as evidence."""
    monkeypatch.setenv("FINOPS_COMMIT_GATE", "strict")
    spec = load_spec(SPEC)
    _git_init(tmp_path)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("scope")
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "site: add things"], cwd=workdir, check=True)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "failed"
    assert p.commit_gate is not None
    assert p.commit_gate["reason"] == "COMMIT_PREFIX"
    assert p.commit_gate["subjects"] == ["site: add things"]
    assert p.commit_gate["expected_prefix"] == "[workflow] scope — g"
    assert "COMMIT_PREFIX" in p.error
    assert "site: add things" in p.error
    assert result.ok is False
    assert result.to_dict()["phases"][0]["commit_gate"]["reason"] == "COMMIT_PREFIX"


def test_commit_prefix_passes_a_matching_commit(tmp_path):
    """(b) A fake agent whose only commit matches '[workflow] <phase> — <goal prefix>' passes
    (the enforcement only fires on the violation)."""
    spec = load_spec(SPEC)
    _git_init(tmp_path)
    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        n = len(calls)
        calls.append(n)
        if n == 0:  # only the scope phase commits — with the correct pattern
            (Path(workdir) / "docs").mkdir(exist_ok=True)
            (Path(workdir) / "docs" / "scope.md").write_text("scope")
            subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "[workflow] scope — g done"], cwd=workdir, check=True)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    assert result.ok
    assert result.phases[0].status == "ok"
    assert result.phases[0].commit_gate is None
    assert all(p.commit_gate is None for p in result.phases)


def test_commit_prefix_fires_even_when_the_phase_already_failed(tmp_path, monkeypatch):
    """The enforcement runs regardless of ok/fail (strict mode): a phase that failed for
    another reason but also made a plain commit carries BOTH reasons."""
    monkeypatch.setenv("FINOPS_COMMIT_GATE", "strict")
    spec = load_spec(SPEC)
    _git_init(tmp_path)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("scope")
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "site: add things"], cwd=workdir, check=True)
        return _fake_agent(ok=False, error="boom")

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "failed"
    assert "boom" in p.error          # the agent's own failure stays visible
    assert "COMMIT_PREFIX" in p.error  # ... and the commit violation is appended
    assert p.commit_gate and p.commit_gate["reason"] == "COMMIT_PREFIX"


def test_commit_prefix_rejects_a_different_phases_name(tmp_path):
    """A commit using ANOTHER phase's name (the resume-spoofing shape) does not count for this
    phase, and the goal prefix is enforced strictly."""
    from agentic_dynamics.runtime import workflow_runner as wr

    assert wr._commit_subject_matches("[workflow] ux_design — g", "scope", "g") is False
    assert wr._commit_subject_matches("[workflow] scope — g", "scope", "g") is True
    assert wr._commit_subject_matches("[workflow] scope — different goal", "scope", "g") is False
    assert wr._commit_subject_matches("site: add things", "scope", "g") is False


def test_commit_prefix_replay_rejects_revamp2_plain_commits(tmp_path, monkeypatch):
    monkeypatch.setenv("FINOPS_COMMIT_GATE", "strict")
    """(c) Replay proof: the revamp2 branch's 7 plain commits would each have failed the phase
    (COMMIT_PREFIX) — the validator rejects every one, accepts the phase's own [workflow]
    commit, and an end-to-end phase that made those 7 commits fails with them as evidence."""
    from agentic_dynamics.runtime import workflow_runner as wr

    goal_prefix = REVAMP2_GOAL[:40]

    # (1) the validator rejects all 7 plain commits ...
    for subject in REVAMP2_PLAIN_COMMITS:
        assert wr._commit_subject_matches(subject, "p1_implement_inventory", goal_prefix) is False, subject
    # ... and accepts the phase's own workflow commit (the runner's _git_commit shape)
    ok = f"[workflow] p1_implement_inventory — {REVAMP2_GOAL}:"
    assert wr._commit_subject_matches(ok, "p1_implement_inventory", goal_prefix) is True

    # (2) end-to-end: an agent that made those 7 commits during the phase fails COMMIT_PREFIX
    spec = load_spec(SPEC)
    _git_init(tmp_path)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        for i, subject in enumerate(REVAMP2_PLAIN_COMMITS):
            (Path(workdir) / "docs" / f"f{i}.md").write_text(subject)
            subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
            subprocess.run(["git", "commit", "-q", "-m", subject], cwd=workdir, check=True)
        return _fake_agent()

    result = run_workflow(spec, goal=REVAMP2_GOAL, model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "failed"
    assert p.commit_gate and p.commit_gate["reason"] == "COMMIT_PREFIX"
    # git log returns newest-first — compare the subject set, not the order
    assert set(p.commit_gate["subjects"]) == set(REVAMP2_PLAIN_COMMITS)
    assert p.commit_gate["expected_prefix"] == f"[workflow] scope — {REVAMP2_GOAL[:40]}"
    assert not p.commit_hash  # the bad commit is never propagated by the commit gate
    assert result.ok is False


def test_commit_prefix_exempts_the_adapters_initial_commit(tmp_path, monkeypatch):
    monkeypatch.setenv("FINOPS_COMMIT_GATE", "strict")
    """The runner's own execution-layer commits are exempt: the adapter's fresh-worktree
    ``Initial`` commit (subject ``Initial`` + the runner's init author) never trips the gate,
    while a plain-message commit under the SAME forged identity still does — the enforcement
    targets MANUAL agent commits (the p4 integration fix the live smoke found)."""
    from agentic_dynamics.runtime import workflow_runner as wr

    spec = load_spec(SPEC)
    _git_init(tmp_path)
    # the worktree starts EMPTY of commits; the fake simulates the adapter's _init_git_workdir
    # creating its "Initial" commit DURING the phase under the runner's init identity
    def agent(prompt, *, model, backend, workdir, **kwargs):
        subprocess.run(["git", "config", "user.email", wr.RUNNER_INIT_AUTHOR_EMAIL], cwd=workdir, check=True)
        subprocess.run(["git", "config", "user.name", "Experiment Runner"], cwd=workdir, check=True)
        (Path(workdir) / "seed.txt").write_text("seed")
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "Initial"], cwd=workdir, check=True)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    assert result.phases[0].status == "ok"
    assert result.phases[0].commit_gate is None

    # same forged identity, but a plain-message commit — NOT exempt (subject != "Initial")
    def agent_bad(prompt, *, model, backend, workdir, **kwargs):
        subprocess.run(["git", "config", "user.email", wr.RUNNER_INIT_AUTHOR_EMAIL], cwd=workdir, check=True)
        subprocess.run(["git", "config", "user.name", "Experiment Runner"], cwd=workdir, check=True)
        (Path(workdir) / "seed2.txt").write_text("changed")  # a NEW change → a real commit
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "site: add things"], cwd=workdir, check=True)
        return _fake_agent()

    spec2 = load_spec(SPEC)
    result2 = run_workflow(spec2, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent_bad)
    assert result2.phases[0].status == "failed"
    assert result2.phases[0].commit_gate["reason"] == "COMMIT_PREFIX"
    assert result2.phases[0].commit_gate["subjects"] == ["site: add things"]


# ── Adversarial verification (cap_runner_hardening p5) ──────────


def test_watchdog_sees_through_a_junk_heartbeat(tmp_path):
    """(p5-1) A stalled agent that touches the session file with junk heartbeats — non-JSON
    lines AND valid-JSON-but-not-a-step dicts — is STILL caught: the stall clock advances only
    on MEANINGFUL step events, never on any write."""
    spec = load_spec(SPEC)
    killed: list[str] = []
    release = threading.Event()

    def agent(prompt, *, model, backend, workdir, watchdog=None, **kwargs):
        transcript = _watchdog_transcript(workdir)
        transcript.parent.mkdir(parents=True, exist_ok=True)
        watchdog["kill"] = lambda: (killed.append("SIGTERM"), release.set())
        transcript.write_text('{"type": "step_start"}\n')  # one real step, then ...
        n = 0
        while not release.is_set():  # ... only junk heartbeats (both flavors)
            with transcript.open("a") as fh:
                fh.write("heartbeat keep-alive\n" if n % 2 else '{"foo": "bar"}\n')
            n += 1
            release.wait(timeout=0.15)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                          phase_watchdog_min=0.03, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "failed"
    assert p.stall_evidence and p.stall_evidence["reason"] == "STALLED"
    assert killed == ["SIGTERM"]


def test_watchdog_cannot_distinguish_a_forged_valid_step(tmp_path):
    """(p5-1, accepted limitation) A heartbeat forged to LOOK like a real step event keeps the
    watchdog alive — the transcript is the model's own output channel and the two are
    indistinguishable at the transcript level. The measured disease was total silence; this is
    documented, not fixed. The test pins the boundary."""
    spec = load_spec(SPEC)
    killed: list[str] = []
    release = threading.Event()

    def agent(prompt, *, model, backend, workdir, watchdog=None, **kwargs):
        transcript = _watchdog_transcript(workdir)
        transcript.parent.mkdir(parents=True, exist_ok=True)
        watchdog["kill"] = lambda: (killed.append("SIGTERM"), release.set())
        with transcript.open("a") as fh:
            fh.write('{"type": "step_start"}\n')
        for _ in range(8):  # keep emitting REAL-looking step boundaries, slowly
            release.wait(timeout=0.2)
            if release.is_set():
                break
            with transcript.open("a") as fh:
                fh.write('{"type": "step_finish"}\n')
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                          phase_watchdog_min=0.03, run_agentic_fn=agent)
    assert result.phases[0].status == "ok"
    assert killed == []


# ── Deploy-gate evasion (p5-2) ──────────────────────────────────

DEPLOY_EVASION_COMMANDS = [
    ("firebase deploy --only hosting", {"workdir": "/somewhere/else"}),  # different cwd
    ("firebase --help > /dev/null && firebase deploy", {}),              # pre-command obfuscation
    ("npx firebase-tools deploy --only hosting", {}),                    # npx form
    ("true; firebase deploy --only hosting", {}),                        # chained
    ("firebase deploy --only hosting --project agentic-dynamics", {}),   # mirror host explicit
]


def test_deploy_gate_evasion_attempts_that_are_caught(tmp_path):
    """(p5-2) Evasion attempts that still expose the firebase command are caught: a different
    working directory, a benign pre-command, the ``npx firebase-tools`` form, chaining, and the
    explicit mirror-host flag. Each fails a non-deploy phase with DEPLOY_GATE."""
    from agentic_dynamics.runtime import workflow_runner as wr

    for command, extra in DEPLOY_EVASION_COMMANDS:
        line = json.dumps({
            "type": "tool_use", "sessionID": "s",
            "part": {"type": "tool", "tool": "bash", "state": {
                "status": "completed",
                "input": {"command": command, "workdir": extra.get("workdir", "/tmp/w")},
                "output": "",
            }},
        })
        assert wr._deploy_pattern_match(command) is not None, command
        spec = load_spec(SPEC)
        result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                              run_agentic_fn=_deploy_agent(line))
        p = result.phases[0]
        assert p.status == "failed", command
        assert p.deploy_gate and p.deploy_gate["reason"] == "DEPLOY_GATE", command
        assert any(command == v["command"] for v in p.deploy_gate["violations"]), command


def test_deploy_gate_catches_a_deploy_script_by_its_output(tmp_path):
    """(p5-2) Indirection caught by the OUTPUT tier: a script file (``./deploy.sh``) whose bash
    input contains no 'firebase' literal but whose captured output shows the production deploy
    banner is still caught — a real firebase deploy prints the banner however it is invoked."""
    line = json.dumps({
        "type": "tool_use", "sessionID": "s",
        "part": {"type": "tool", "tool": "bash", "state": {
            "status": "completed",
            "input": {"command": "./deploy.sh", "workdir": "/tmp/wt_site_revamp2/apps/website"},
            "output": "\n=== Deploying to 'ai-finops-rulebook'...\n\u2714 Deploy complete!\n"
                      "Hosting URL: https://ai-finops-rulebook.web.app\n",
        }},
    })
    spec = load_spec(SPEC)
    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                          run_agentic_fn=_deploy_agent(line))
    p = result.phases[0]
    assert p.status == "failed"
    assert p.deploy_gate and p.deploy_gate["reason"] == "DEPLOY_GATE"
    assert p.deploy_gate["violations"][0]["command"] == "./deploy.sh"
    assert "Deploy complete!" in p.deploy_gate["violations"][0]["pattern"]


def test_deploy_gate_variable_indirection_without_a_banner_is_a_limitation(tmp_path):
    """(p5-2, accepted limitation) Indirection that never surfaces the literal 'firebase'
    command NOR the deploy banner in this phase's transcript — e.g. an alias/variable defined in
    an EARLIER phase, or a wrapper that suppresses firebase's output — is not catchable by a
    deterministic transcript scan (shell state across phases is unresolvable). Documented, not
    fixed. The test pins the boundary so a future hardening knows where it stands."""
    from agentic_dynamics.runtime import workflow_runner as wr

    line = json.dumps({
        "type": "tool_use", "sessionID": "s",
        "part": {"type": "tool", "tool": "bash", "state": {
            "status": "completed",
            "input": {"command": "$DEPLOY --only hosting --project agentic-dynamics",
                      "workdir": "/tmp/apps/website"},
            "output": "ok",  # a wrapper that swallows the deploy banner
        }},
    })
    transcript = Path(tmp_path) / "lim.jsonl"
    transcript.write_text(line + "\n")
    assert wr._scan_transcript_for_deploys(transcript) == []


# ── Commit-enforcement evasion (p5-3) ───────────────────────────


def test_commit_prefix_evasion_attempts_that_are_caught(tmp_path):
    """(p5-3) Commit-message evasion: a DIFFERENT phase's name, a hyphen instead of the literal
    em-dash, a double em-dash, and a missing space after the em-dash are all rejected — the
    validator enforces the phase's OWN name + the exact pattern the resume machinery matches."""
    from agentic_dynamics.runtime import workflow_runner as wr

    goal_prefix = "g"
    assert wr._commit_subject_matches("[workflow] p3_dom_verification — g", "scope", goal_prefix) is False
    assert wr._commit_subject_matches("[workflow] scope - g", "scope", goal_prefix) is False
    assert wr._commit_subject_matches("[workflow] scope -- g", "scope", goal_prefix) is False
    assert wr._commit_subject_matches("[workflow] scope —— g", "scope", goal_prefix) is False
    assert wr._commit_subject_matches("[workflow] scope —g", "scope", goal_prefix) is False
    assert wr._commit_subject_matches("[workflow] scope — g", "scope", goal_prefix) is True
    # a WRONG goal prefix is rejected (already covered, kept for the attack matrix)
    assert wr._commit_subject_matches("[workflow] scope — different goal", "scope", goal_prefix) is False


def test_commit_prefix_trailing_content_after_a_valid_prefix_matches(tmp_path):
    """(p5-3, known-safe) Trailing content AFTER a valid '[workflow] <phase> — <goal prefix>'
    prefix still matches — the SAME startswith leniency the resume machinery has. The
    enforcement is deliberately not stricter than the pattern it guards: a commit that resumes
    as this phase's IS this phase's. Not a bypass of the contract; documented."""
    from agentic_dynamics.runtime import workflow_runner as wr

    assert wr._commit_subject_matches("[workflow] scope — g; rm -rf /", "scope", "g") is True
    assert wr._commit_subject_matches("[workflow] scope — g (done, extra)", "scope", "g") is True




