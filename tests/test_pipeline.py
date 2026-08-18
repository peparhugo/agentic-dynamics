"""Tests for pipeline.py — YAML-driven phase orchestration."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline import (
    EXECUTORS,
    PlanDefinition,
    PlanPhase,
    PlanState,
    Workstream,
    _detect_conflicts,
    _detect_cycles,
    _execute_pipeline,
    _execute_shell,
    _interpolate_levels,
    _parse_phase,
    _parse_workstreams,
    _resolve_cwd,
    _substitute_template,
    load_plans,
    topological_order,
    validate_plan,
    workstream_waves,
)

VALID_PLANS_YAML = """
plans:
  simple:
    description: "Simple CI pipeline"
    phases:
      - id: lint
        kind: lint
      - id: test
        kind: test
        depends_on: [lint]
      - id: build
        kind: shell
        cmd: [python, scripts/build_data.py]
        depends_on: [test]

  matrix:
    description: "Full matrix"
    phases:
      - id: baseline
        kind: matrix
        model: deepseek/deepseek-v4-pro
        model_filter: deepseek
        stories: [task_manager_api]
        tiers: [tier1_minimal]
        conditions:
          good: [clean]
          bad: [clean]
        workers: 4
      - id: analyze
        kind: shell
        depends_on: [baseline]
        cmd: [python, scripts/analyze_worktrees.py]
"""

CYCLE_YAML = """
plans:
  broken:
    description: "Has a cycle"
    phases:
      - id: a
        kind: shell
        cmd: [echo, a]
        depends_on: [c]
      - id: b
        kind: shell
        cmd: [echo, b]
        depends_on: [a]
      - id: c
        kind: shell
        cmd: [echo, c]
        depends_on: [b]
"""

MISSING_DEP_YAML = """
plans:
  broken:
    description: "Missing dependency"
    phases:
      - id: a
        kind: shell
        cmd: [echo, a]
        depends_on: [z]
      - id: b
        kind: shell
        cmd: [echo, b]
"""


class TestPlanPhase:
    def test_dataclass_defaults(self):
        p = PlanPhase(id="test", kind="shell")
        assert p.id == "test"
        assert p.kind == "shell"
        assert p.description == ""
        assert p.depends_on == []
        assert p.kind_params == {}

    def test_kind_params_from_dict(self):
        p = PlanPhase(id="test", kind="shell", kind_params={"cmd": ["python", "script.py"], "timeout": 300})
        assert p.kind_params == {"cmd": ["python", "script.py"], "timeout": 300}


class TestPlanState:
    def test_roundtrip(self):
        s = PlanState(status="running", jobs_total=5, jobs_done=3)
        d = s.to_dict()
        s2 = PlanState.from_dict(d)
        assert s2.status == "running"
        assert s2.jobs_total == 5
        assert s2.jobs_done == 3

    def test_defaults(self):
        s = PlanState()
        assert s.status == "pending"
        assert s.jobs_total == 0
        assert s.jobs_done == 0

    def test_from_dict_missing_fields(self):
        s = PlanState.from_dict({})
        assert s.status == "pending"


class TestLoadPlans:
    def test_load_valid_plans(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(VALID_PLANS_YAML)
            path = Path(f.name)

        try:
            plans = load_plans(path)
            assert set(plans) == {"simple", "matrix"}

            simple = plans["simple"]
            assert simple.name == "simple"
            assert len(simple.phases) == 3
            assert simple.phases[0].id == "lint"
            assert simple.phases[0].kind == "lint"
            assert simple.phases[0].depends_on == []
            assert simple.phases[1].depends_on == ["lint"]
            assert simple.phases[2].depends_on == ["test"]
            assert simple.phases[2].kind_params == {"cmd": ["python", "scripts/build_data.py"]}

            matrix = plans["matrix"]
            assert matrix.phases[0].kind == "matrix"
            assert matrix.phases[0].kind_params["model"] == "deepseek/deepseek-v4-pro"
            assert matrix.phases[0].kind_params["workers"] == 4
        finally:
            path.unlink()


class TestValidatePlan:
    def test_valid_plan(self):
        phases = [
            PlanPhase(id="a", kind="shell", depends_on=[]),
            PlanPhase(id="b", kind="shell", depends_on=["a"]),
        ]
        plan = PlanDefinition(name="test", description="", phases=phases)
        assert validate_plan(plan) == []

    def test_missing_dependency(self):
        phases = [
            PlanPhase(id="a", kind="shell", depends_on=["z"]),
            PlanPhase(id="b", kind="shell", depends_on=[]),
        ]
        plan = PlanDefinition(name="test", description="", phases=phases)
        errors = validate_plan(plan)
        assert len(errors) == 1
        assert "unknown phase 'z'" in errors[0]

    def test_cycle_detection(self):
        phases = [
            PlanPhase(id="a", kind="shell", depends_on=["c"]),
            PlanPhase(id="b", kind="shell", depends_on=["a"]),
            PlanPhase(id="c", kind="shell", depends_on=["b"]),
        ]
        plan = PlanDefinition(name="test", description="", phases=phases)
        errors = validate_plan(plan)
        assert len(errors) == 1
        assert "Cycle" in errors[0]

    def test_empty_plan(self):
        plan = PlanDefinition(name="test", description="", phases=[])
        errors = validate_plan(plan)
        assert len(errors) == 1
        assert "no phases" in errors[0].lower()

    def test_self_loop(self):
        phases = [
            PlanPhase(id="a", kind="shell", depends_on=["a"]),
        ]
        plan = PlanDefinition(name="test", description="", phases=phases)
        errors = validate_plan(plan)
        assert len(errors) == 1
        assert "Cycle" in errors[0]

    def test_load_cycle_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(CYCLE_YAML)
            path = Path(f.name)
        try:
            plans = load_plans(path)
            errors = validate_plan(plans["broken"])
            assert len(errors) == 1
            assert "Cycle" in errors[0]
        finally:
            path.unlink()

    def test_load_missing_dep_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(MISSING_DEP_YAML)
            path = Path(f.name)
        try:
            plans = load_plans(path)
            errors = validate_plan(plans["broken"])
            assert len(errors) == 1
            assert "unknown phase" in errors[0]
        finally:
            path.unlink()


class TestTopologicalOrder:
    def test_linear(self):
        phases = [
            PlanPhase(id="a", kind="shell"),
            PlanPhase(id="b", kind="shell", depends_on=["a"]),
            PlanPhase(id="c", kind="shell", depends_on=["b"]),
        ]
        plan = PlanDefinition(name="test", description="", phases=phases)
        levels = topological_order(plan)
        assert levels == [["a"], ["b"], ["c"]]

    def test_parallel(self):
        phases = [
            PlanPhase(id="a", kind="shell"),
            PlanPhase(id="b", kind="shell"),
            PlanPhase(id="c", kind="shell", depends_on=["a", "b"]),
        ]
        plan = PlanDefinition(name="test", description="", phases=phases)
        levels = topological_order(plan)
        assert levels == [["a", "b"], ["c"]]

    def test_diamond(self):
        phases = [
            PlanPhase(id="a", kind="shell"),
            PlanPhase(id="b", kind="shell", depends_on=["a"]),
            PlanPhase(id="c", kind="shell", depends_on=["a"]),
            PlanPhase(id="d", kind="shell", depends_on=["b", "c"]),
        ]
        plan = PlanDefinition(name="test", description="", phases=phases)
        levels = topological_order(plan)
        assert levels == [["a"], ["b", "c"], ["d"]]

    def test_single_phase(self):
        phases = [PlanPhase(id="a", kind="shell")]
        plan = PlanDefinition(name="test", description="", phases=phases)
        levels = topological_order(plan)
        assert levels == [["a"]]

    def test_independent_parallel(self):
        phases = [
            PlanPhase(id="a", kind="shell"),
            PlanPhase(id="b", kind="shell"),
        ]
        plan = PlanDefinition(name="test", description="", phases=phases)
        levels = topological_order(plan)
        assert levels == [["a", "b"]]


class TestDetectCycles:
    def test_no_cycles(self):
        phases = [
            PlanPhase(id="a", kind="shell"),
            PlanPhase(id="b", kind="shell", depends_on=["a"]),
        ]
        plan = PlanDefinition(name="test", description="", phases=phases)
        assert _detect_cycles(plan) is None

    def test_simple_cycle(self):
        phases = [
            PlanPhase(id="a", kind="shell", depends_on=["b"]),
            PlanPhase(id="b", kind="shell", depends_on=["a"]),
        ]
        plan = PlanDefinition(name="test", description="", phases=phases)
        result = _detect_cycles(plan)
        assert result is not None
        assert "a" in result and "b" in result

    def test_three_node_cycle(self):
        phases = [
            PlanPhase(id="a", kind="shell", depends_on=["c"]),
            PlanPhase(id="b", kind="shell", depends_on=["a"]),
            PlanPhase(id="c", kind="shell", depends_on=["b"]),
        ]
        plan = PlanDefinition(name="test", description="", phases=phases)
        result = _detect_cycles(plan)
        assert result is not None
        assert len(result) == 4  # a → c → b → a


class TestInterpolateLevels:
    def test_no_filters(self):
        levels = [["a"], ["b"], ["c"]]
        assert _interpolate_levels(levels, None, None, None) == levels

    def test_from_phase(self):
        levels = [["a"], ["b"], ["c"], ["d"]]
        assert _interpolate_levels(levels, "b", None, None) == [["b"], ["c"], ["d"]]

    def test_from_phase_full_level(self):
        levels = [["a", "x"], ["b", "y"], ["c"]]
        assert _interpolate_levels(levels, "y", None, None) == [["b", "y"], ["c"]]

    def test_until_phase(self):
        levels = [["a"], ["b"], ["c"], ["d"]]
        assert _interpolate_levels(levels, None, "c", None) == [["a"], ["b"], ["c"]]

    def test_only_phases(self):
        levels = [["a"], ["b"], ["c"], ["d"]]
        assert _interpolate_levels(levels, None, None, ["b", "d"]) == [["b"], ["d"]]

    def test_from_and_until(self):
        levels = [["a"], ["b"], ["c"], ["d"], ["e"]]
        result = _interpolate_levels(levels, "b", "d", None)
        assert result == [["b"], ["c"], ["d"]]

    def test_from_and_only(self):
        levels = [["a", "x"], ["b", "y"], ["c", "z"]]
        result = _interpolate_levels(levels, "b", None, ["b", "z"])
        assert result == [["b"], ["z"]]

    def test_from_phase_not_found(self):
        levels = [["a"], ["b"]]
        result = _interpolate_levels(levels, "q", None, None)
        assert result == []


class TestSubstituteTemplate:
    def test_no_substitution(self):
        assert _substitute_template(["echo", "hello"], {}) == ["echo", "hello"]

    def test_with_prompt(self):
        result = _substitute_template(
            ["opencode", "run", "{prompt}", "--model", "deepseek"],
            {"prompt": "add dark mode"},
        )
        assert result == ["opencode", "run", "add dark mode", "--model", "deepseek"]

    def test_multiple_placeholders(self):
        result = _substitute_template(
            ["run", "--name", "{name}", "--tag", "{tag}"],
            {"name": "ci", "tag": "v2"},
        )
        assert result == ["run", "--name", "ci", "--tag", "v2"]


class TestShellExecutor:
    def test_success(self):
        phase = PlanPhase(id="test", kind="shell", kind_params={"cmd": ["echo", "hello"]})
        assert _execute_shell(phase, {}) is True

    def test_failure(self):
        phase = PlanPhase(id="test", kind="shell", kind_params={"cmd": ["false"]})
        assert _execute_shell(phase, {}) is False

    def test_unknown_command(self):
        phase = PlanPhase(id="test", kind="shell", kind_params={"cmd": ["nonexistent_command_xyz"]})
        assert _execute_shell(phase, {}) is False

    def test_empty_cmd(self):
        phase = PlanPhase(id="test", kind="shell")
        assert _execute_shell(phase, {}) is True


class TestPipelineExecutor:
    def test_all_success(self):
        phase = PlanPhase(id="test", kind="pipeline", kind_params={"steps": [["echo", "step1"], ["echo", "step2"]]})
        assert _execute_pipeline(phase, {}) is True

    def test_stop_on_failure(self):
        phase = PlanPhase(id="test", kind="pipeline", kind_params={"steps": [["echo", "step1"], ["false"], ["echo", "step3"]]})
        assert _execute_pipeline(phase, {}) is False

    def test_template_substitution(self):
        phase = PlanPhase(id="test", kind="pipeline", kind_params={"steps": [["echo", "{greeting}"], ["echo", "{name}"]]})
        assert _execute_pipeline(phase, {"greeting": "hello", "name": "world"}) is True


class TestExecutorDispatch:
    def test_all_kinds_registered(self):
        expected = {
            "shell", "test", "lint", "matrix", "review", "pipeline", "ship",
            "fan_out", "conflict_detect", "pr_create", "pr_merge",
        }
        assert set(EXECUTORS) == expected

    def test_unknown_kind_is_none(self):
        assert EXECUTORS.get("nonexistent") is None


class TestPythonModulesLoad:
    """Verify the plan YAML file is loadable and all plans are valid."""

    def test_load_plans_yaml(self):
        plan_path = (
            Path(__file__).resolve().parent.parent
            / "experiments" / "configs" / "plans.yaml"
        )
        plans = load_plans(plan_path)
        assert {"ci", "deploy", "full_matrix", "feature", "ship_features"} <= set(plans)

        for name, plan in plans.items():
            errors = validate_plan(plan)
            assert errors == [], f"Plan '{name}' has errors: {errors}"

    def test_plan_ci_correct_deps(self):
        plan_path = (
            Path(__file__).resolve().parent.parent
            / "experiments" / "configs" / "plans.yaml"
        )
        plans = load_plans(plan_path)
        ci = plans["ci"]
        levels = topological_order(ci)
        assert len(levels) == 3
        assert "lint" in levels[0] and "typecheck" in levels[0]
        assert levels[1] == ["test"]
        assert levels[2] == ["build"]

    def test_plan_feature_correct_deps(self):
        plan_path = (
            Path(__file__).resolve().parent.parent
            / "experiments" / "configs" / "plans.yaml"
        )
        plans = load_plans(plan_path)
        feature = plans["feature"]
        levels = topological_order(feature)
        assert levels[0] == ["spec"]
        assert levels[1] == ["implement"]
        assert "lint" in levels[2] and "test" in levels[2]


class TestWorkstream:
    def test_defaults(self):
        ws = Workstream(name="auth", branch="feature/auth")
        assert ws.name == "auth"
        assert ws.branch == "feature/auth"
        assert ws.phases == []
        assert ws.depends_on == []


class TestParsePhase:
    def test_simple_phase(self):
        p = _parse_phase({"id": "a", "kind": "shell", "cmd": ["echo", "hi"]})
        assert p.id == "a"
        assert p.kind == "shell"
        assert p.kind_params == {"cmd": ["echo", "hi"]}

    def test_fan_out_phase(self):
        p = _parse_phase({
            "id": "build",
            "kind": "fan_out",
            "workstreams": {
                "auth": {
                    "branch": "feature/auth",
                    "phases": [
                        {"id": "spec", "kind": "shell", "cmd": ["echo", "spec"]},
                        {"id": "impl", "kind": "shell", "depends_on": ["spec"]},
                    ],
                },
            },
        })
        assert p.kind == "fan_out"
        workstreams = p.kind_params["workstreams"]
        assert "auth" in workstreams
        ws = workstreams["auth"]
        assert isinstance(ws, Workstream)
        assert ws.branch == "feature/auth"
        assert len(ws.phases) == 2
        assert ws.phases[0].id == "spec"
        assert ws.phases[1].depends_on == ["spec"]


class TestParseWorkstreams:
    def test_default_branch(self):
        workstreams = _parse_workstreams({
            "auth": {"phases": [{"id": "spec", "kind": "shell", "cmd": ["echo", "x"]}]},
        })
        assert workstreams["auth"].branch == "feature/auth"

    def test_explicit_branch(self):
        workstreams = _parse_workstreams({
            "auth": {"branch": "feature/oauth", "phases": []},
        })
        assert workstreams["auth"].branch == "feature/oauth"

    def test_depends_on(self):
        workstreams = _parse_workstreams({
            "a": {"phases": [], "depends_on": ["b"]},
            "b": {"phases": []},
        })
        assert workstreams["a"].depends_on == ["b"]
        assert workstreams["b"].depends_on == []


class TestWorkstreamWaves:
    def test_independent_parallel(self):
        ws = {
            "a": Workstream(name="a", branch="feature/a"),
            "b": Workstream(name="b", branch="feature/b"),
        }
        waves = workstream_waves(ws)
        assert waves == [["a", "b"]]

    def test_sequential_dependency(self):
        ws = {
            "a": Workstream(name="a", branch="feature/a"),
            "b": Workstream(name="b", branch="feature/b", depends_on=["a"]),
        }
        waves = workstream_waves(ws)
        assert waves == [["a"], ["b"]]

    def test_diamond(self):
        ws = {
            "a": Workstream(name="a", branch="feature/a"),
            "b": Workstream(name="b", branch="feature/b", depends_on=["a"]),
            "c": Workstream(name="c", branch="feature/c", depends_on=["a"]),
            "d": Workstream(name="d", branch="feature/d", depends_on=["b", "c"]),
        }
        waves = workstream_waves(ws)
        assert waves == [["a"], ["b", "c"], ["d"]]

    def test_mixed(self):
        ws = {
            "auth": Workstream(name="auth", branch="feature/auth"),
            "api": Workstream(name="api", branch="feature/api"),
            "docs": Workstream(name="docs", branch="feature/docs", depends_on=["api"]),
        }
        waves = workstream_waves(ws)
        assert waves == [["api", "auth"], ["docs"]]


class TestResolveCwd:
    def test_context_override(self):
        phase = PlanPhase(id="a", kind="shell", kind_params={"cwd": "/default"})
        assert _resolve_cwd(phase, {"cwd": "/override"}) == "/override"

    def test_kind_params_fallback(self):
        phase = PlanPhase(id="a", kind="shell", kind_params={"cwd": "/default"})
        assert _resolve_cwd(phase, {}) == "/default"

    def test_root_default(self):
        phase = PlanPhase(id="a", kind="shell")
        result = _resolve_cwd(phase, {})
        # Feature worktrees have arbitrary basenames; the default is this repository root.
        assert Path(result) == Path(__file__).resolve().parent.parent


class TestDetectConflicts:
    def test_clean_merge_returns_empty(self):
        result = _detect_conflicts("HEAD", "HEAD")
        assert result == []

    def test_ancestor_returns_empty(self):
        result = _detect_conflicts("main", "main")
        assert result == []


class TestDetectConflictsIntegration:
    def _make_repo(self, tmp_path):
        import subprocess

        def git(*args):
            return subprocess.run(
                ["git", *args], cwd=str(tmp_path), capture_output=True, text=True, check=True,
            )

        git("init", "-q")
        git("config", "user.email", "t@t.com")
        git("config", "user.name", "t")
        (tmp_path / "f.txt").write_text("line1\n")
        git("add", "-A")
        git("commit", "-qm", "init")
        git("branch", "-M", "main")
        return git

    def test_clean_merge(self, tmp_path):
        git = self._make_repo(tmp_path)
        (tmp_path / "g.txt").write_text("new\n")
        git("add", "-A")
        git("commit", "-qm", "main change")
        # branch off the original init, touching a different file
        git("checkout", "-qb", "feature/a", "HEAD~1")
        (tmp_path / "other.txt").write_text("x\n")
        git("add", "-A")
        git("commit", "-qm", "a change")
        git("checkout", "-q", "main")
        conflicts = _detect_conflicts("main", "feature/a", cwd=str(tmp_path))
        assert conflicts == []

    def test_conflict_detected(self, tmp_path):
        git = self._make_repo(tmp_path)
        # main diverges
        (tmp_path / "f.txt").write_text("lineMain\n")
        git("add", "-A")
        git("commit", "-qm", "main change")
        # feature/a diverges from original init, same file
        git("checkout", "-qb", "feature/a", "HEAD~1")
        (tmp_path / "f.txt").write_text("lineA\n")
        git("add", "-A")
        git("commit", "-qm", "a change")
        git("checkout", "-q", "main")
        conflicts = _detect_conflicts("main", "feature/a", cwd=str(tmp_path))
        assert "f.txt" in conflicts


class TestFanOutYaml:
    def test_load_ship_features(self):
        plan_path = (
            Path(__file__).resolve().parent.parent
            / "experiments" / "configs" / "plans.yaml"
        )
        plans = load_plans(plan_path)
        sf = plans["ship_features"]

        build = sf.phases[0]
        assert build.kind == "fan_out"
        workstreams = build.kind_params["workstreams"]
        assert set(workstreams) == {"auth", "api", "docs"}

        waves = workstream_waves(workstreams)
        assert waves == [["api", "auth"], ["docs"]]

        # Cross-cut phases reference the fan_out
        conflicts = sf.phases[1]
        assert conflicts.kind == "conflict_detect"
        assert conflicts.kind_params["from_fanout"] == "build"
        assert conflicts.depends_on == ["build"]

        prs = sf.phases[2]
        assert prs.kind == "pr_create"
        assert prs.depends_on == ["conflicts"]

        merge = sf.phases[3]
        assert merge.kind == "pr_merge"
        assert merge.kind_params["conflict_strategy"] == "rebase"
        assert merge.kind_params["squash"] is True
        assert merge.depends_on == ["prs"]

    def test_nested_phase_depends_on(self):
        plan_path = (
            Path(__file__).resolve().parent.parent
            / "experiments" / "configs" / "plans.yaml"
        )
        plans = load_plans(plan_path)
        sf = plans["ship_features"]
        ws = sf.phases[0].kind_params["workstreams"]["auth"]
        assert ws.phases[0].id == "spec"
        assert ws.phases[1].depends_on == ["spec"]
        assert ws.phases[2].depends_on == ["impl"]


# ── canonical-state round 2, plan step 11: run.py:_save_results write-time
# registration. run.py is a DIFFERENT script from pipeline.py (this file's main
# subject) but shares this file's existing `scripts/` sys.path bootstrap above, and no
# other test file covers `_save_results` at all — extending in place here rather than
# adding a fourth test file for the same call-site pattern already covered by
# test_story.py (save_story_result) and test_finalize_reviews.py (_finalize_story).
class TestSaveResultsRegistryEmission:
    def _runs(self):
        return [{"operator": "baseline", "correctness": 0.9, "cost_usd": 0.5, "total_tokens": 1000}]

    def test_skips_emission_when_kb_write_unset(self, tmp_path, monkeypatch):
        import run
        from instrument import knowledge_stream as ks

        monkeypatch.delenv("FINOPS_KB_WRITE", raising=False)

        def _explode(*a, **kw):
            raise AssertionError("must not connect to the knowledge stream when KB_WRITE is unset")

        monkeypatch.setattr(ks, "connect", _explode)

        run._save_results(self._runs(), "task_manager_api", "DeepSeek v4 Flash", tmp_path)
        # No assertion error raised above == no connection attempt was made.

    def test_emits_registry_event_when_kb_write_enabled(self, tmp_path, monkeypatch):
        import run
        from instrument import knowledge_stream as ks

        monkeypatch.setenv("FINOPS_KB_WRITE", "1")
        published = []
        monkeypatch.setattr(ks, "connect", lambda: object())
        monkeypatch.setattr(
            ks, "publish_event",
            lambda r, event, **kw: published.append((event, kw)) or "0-1",
        )

        run._save_results(self._runs(), "task_manager_api", "DeepSeek v4 Flash", tmp_path)

        assert len(published) == 1
        event, kwargs = published[0]
        assert kwargs["source_type"] == "story"
        assert kwargs["authorized"] is True
        assert event.knowledge_id

    def test_result_file_is_still_written_regardless_of_kb_write(self, tmp_path, monkeypatch):
        import run

        monkeypatch.delenv("FINOPS_KB_WRITE", raising=False)
        run._save_results(self._runs(), "task_manager_api", "DeepSeek v4 Flash", tmp_path)
        out_path = tmp_path / "task_manager_api_deepseek_v4_flash.json"
        assert out_path.exists()
