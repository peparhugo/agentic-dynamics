"""The contemplation fan-out workflow: fixed-parent forks + the synthesis channel."""

from __future__ import annotations

from pathlib import Path

from agentic_dynamics.experiment.experiment_spec import load_spec
from agentic_dynamics.runtime.workflow_runner import run_workflow

SPEC = """name: t
question: q
version: "0.1"
artifact_kind: workflow
intent: measure
side_effects: {repository: false, external_services: false}
repeatable: true
factors: [{name: model, levels: [m]}]
design: factorial
rules: []
metrics: []
comparison: null
writeup: {format: lab_book, sections: [question]}
stop: {budget_usd: 1.0, max_attempts: 1}
adapt: {strategy: manual, selection: highest_uncertainty}
workflow:
  kind: agent_task
  params:
    language: python
    fork: false
    rag_augment: false
    context:
      domain_context: TEST CONTEXT
    phases:
      - name: one
        kind: agent
        scope: research_readonly
        fork_session: ses_fixed_parent
        timeout: 60
        prompt: |
          first task
      - name: two
        kind: agent
        scope: research_readonly
        fork_session: ses_fixed_parent
        timeout: 60
        prompt: |
          second task using {prior_answers}
"""


def test_fixed_parent_fork_and_the_synthesis_channel(tmp_path):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "seed.txt").write_text("seed")
    subprocess.run(["git", "add", "seed.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=tmp_path, check=True)
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(SPEC, encoding="utf-8")
    spec = load_spec(spec_path)
    calls = []

    class R:
        ok = True
        error = ""
        session_id = "ses_child"
        total_tokens = 10
        estimated_cost_usd = 0.0

    def fake(prompt, **kwargs):
        calls.append({"prompt": prompt, "kwargs": kwargs})
        R.final_response = f"answer-{len(calls)}"
        R.session_id = f"ses_child_{len(calls)}"
        return R()

    run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=fake)
    assert len(calls) == 2
    # every phase forks the FIXED parent (not the previous phase's session)
    assert calls[0]["kwargs"].get("session_id") == "ses_fixed_parent"
    assert calls[1]["kwargs"].get("session_id") == "ses_fixed_parent"
    assert calls[0]["kwargs"].get("fork") is True and calls[1]["kwargs"].get("fork") is True
    # the synthesis channel carries the prior phase's ANSWER into the later prompt
    assert "answer-1" in calls[1]["prompt"]


# ── fork-answer delivery repair (2026-09-20) ─────────────────────────────────────────────────

PRESEED_SPEC = """name: t2
question: q
version: "0.1"
artifact_kind: workflow
intent: measure
side_effects: {repository: false, external_services: false}
repeatable: true
factors: [{name: model, levels: [m]}]
design: factorial
rules: []
metrics: []
comparison: null
writeup: {format: lab_book, sections: [question]}
stop: {budget_usd: 1.0, max_attempts: 1}
adapt: {strategy: manual, selection: highest_uncertainty}
workflow:
  kind: agent_task
  params:
    language: python
    fork: false
    rag_augment: false
    prior_answers:
      - {name: ev/a, path: __EVIDENCE_A__}
      - {name: ev/b, path: __EVIDENCE_B__}
    context:
      domain_context: TEST CONTEXT
    phases:
      - name: synthesis
        kind: agent
        scope: research_readonly
        fork_session: ses_fixed_parent
        timeout: 60
        prompt: |
          synthesize {prior_answers}
"""


def _init_repo(tmp_path):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "seed.txt").write_text("seed")
    subprocess.run(["git", "add", "seed.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=tmp_path, check=True)


def test_answers_are_delivered_complete_with_a_manifest(tmp_path):
    _init_repo(tmp_path)
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(SPEC, encoding="utf-8")
    spec = load_spec(spec_path)
    big = "ANSWER-START " + ("x" * 5000) + " TAIL-MARKER"
    prompts = []

    class R:
        ok = True
        error = ""
        session_id = "ses_child"
        total_tokens = 10
        estimated_cost_usd = 0.0
        final_response = ""

    def fake(prompt, **kwargs):
        prompts.append(prompt)
        R.final_response = big if len(prompts) == 1 else "synthesis"
        R.session_id = f"ses_child_{len(prompts)}"
        return R()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=fake)
    # COMPLETE pass-through: the 5,000+ char answer's tail reaches the synthesis prompt
    assert "TAIL-MARKER" in prompts[1]
    assert "ANSWER EVIDENCE" in prompts[1] and "complete" in prompts[1]
    # the manifest records exactly what was delivered
    manifest = result.answers_delivered
    assert len(manifest) == 1
    assert manifest[0]["name"] == "one"
    assert manifest[0]["chars"] == len(big)
    assert manifest[0]["complete"] is True
    assert manifest[0]["session_id"] == "ses_child_1"
    assert len(manifest[0]["sha256"]) == 64
    # the ledger carries the manifest AND the phase's complete final response
    ledger = result.to_dict()
    assert ledger["answers_delivered"][0]["chars"] == len(big)
    assert ledger["phases"][0]["final_response"] == big
    assert ledger["phases"][1]["final_response"] == "synthesis"


def test_preseed_delivers_declared_evidence_completely(tmp_path):
    _init_repo(tmp_path)
    ev_a = tmp_path / "a.md"
    ev_b = tmp_path / "b.md"
    ev_a.write_text("A-" + ("a" * 4200) + "-A-END", encoding="utf-8")
    ev_b.write_text("B-" + ("b" * 3000) + "-B-END", encoding="utf-8")
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(
        PRESEED_SPEC.replace("__EVIDENCE_A__", str(ev_a)).replace("__EVIDENCE_B__", str(ev_b)),
        encoding="utf-8",
    )
    spec = load_spec(spec_path)
    prompts = []

    class R:
        ok = True
        error = ""
        session_id = "ses_child"
        total_tokens = 10
        estimated_cost_usd = 0.0
        final_response = "ok"

    def fake(prompt, **kwargs):
        prompts.append(prompt)
        return R()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=fake)
    assert "A-END" in prompts[0] and "B-END" in prompts[0]
    assert "ANSWER EVIDENCE — 2 outputs delivered" in prompts[0]
    manifest = result.answers_delivered
    assert [e["name"] for e in manifest] == ["ev/a", "ev/b"]
    assert all(e["complete"] is True and e["path"] for e in manifest)
    assert manifest[0]["chars"] == len(ev_a.read_text(encoding="utf-8"))


def test_preseed_refuses_missing_evidence(tmp_path):
    import pytest

    _init_repo(tmp_path)
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(
        PRESEED_SPEC.replace("__EVIDENCE_A__", str(tmp_path / "missing.md")).replace(
            "__EVIDENCE_B__", str(tmp_path / "b.md")
        ),
        encoding="utf-8",
    )
    spec = load_spec(spec_path)

    def fake(prompt, **kwargs):  # pragma: no cover — must never be called
        raise AssertionError("the run must refuse before any provider call")

    with pytest.raises(ValueError, match="prior_answers evidence missing"):
        run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=fake)


def test_fork_answers_bundle_above_the_inline_budget(tmp_path):
    _init_repo(tmp_path)

    ev_a = tmp_path / "a.md"
    ev_b = tmp_path / "b.md"
    big_a = "A-" + ("a" * 60_000) + "-A-END"
    big_b = "B-" + ("b" * 60_000) + "-B-END"
    ev_a.write_text(big_a, encoding="utf-8")
    ev_b.write_text(big_b, encoding="utf-8")
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(
        PRESEED_SPEC.replace("__EVIDENCE_A__", str(ev_a)).replace("__EVIDENCE_B__", str(ev_b)),
        encoding="utf-8",
    )
    spec = load_spec(spec_path)
    prompts = []

    class R:
        ok = True
        error = ""
        session_id = "ses_child"
        total_tokens = 10
        estimated_cost_usd = 0.0
        final_response = "ok"

    def fake(prompt, **kwargs):
        prompts.append(prompt)
        return R()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=fake)
    # above the budget the payload is a FILE INDEX, not the inline text (argv safety)
    assert "delivered as FILES" in prompts[0]
    assert "A-END" not in prompts[0] and "B-END" not in prompts[0]
    assert len(prompts[0]) < 130_000
    manifest = result.answers_delivered
    assert len(manifest) == 2 and all(e["file"] and e["path"] for e in manifest)
    # each delivered file contains the COMPLETE text — nothing truncated
    for entry, big in zip(manifest, (big_a, big_b), strict=True):
        assert Path(entry["file"]).read_text(encoding="utf-8") == big
        assert entry["complete"] is True
