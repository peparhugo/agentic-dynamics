"""Runtime — the agent execution runtime (critique system 3).

Ownership: phase execution inside a git worktree (``workflow_runner``), the independent test
runner (``test_runner``), multi-session story orchestration (``story``), and post-hoc job
transport (``posthoc``).

Pinned execution→control observation edge: ``workflow_runner`` → ``control.step_routing`` /
``control.live`` — execution consults the per-step router and publishes telemetry, observe-only
(never steered back through the same edge).
"""
