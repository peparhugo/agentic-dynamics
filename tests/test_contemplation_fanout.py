"""The contemplation fan-out workflow: fixed-parent forks + the synthesis channel."""

from __future__ import annotations

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
