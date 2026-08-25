"""Runtime — the agent execution runtime (critique system 3).

Ownership: phase execution inside a git worktree (``workflow_runner``), the independent test
runner (``test_runner``), multi-session story orchestration (``story``), post-hoc job transport
(``posthoc``), and the runtime-owned routing/telemetry/change-analyzer *contracts* (``routing`` /
``telemetry`` / ``change_analyzer``).

Dependency-inverted seam (refactor-repair Debt-2): ``workflow_runner`` no longer imports
``control`` — it consumes the ``Router`` and ``TelemetryPublisher`` protocols defined here, with
the control implementations injected at the composition root (``scripts/run_workflow.py``).
Runtime depends on the protocol; control supplies the decision. Same for the evidence-integrity
seam (design §5.7): ``change_analyzer`` owns the ``ChangeAnalyzer`` protocol; the concrete
implementation (``control.evidence_analyzer``) is injected at the root, default no-op.
"""

from . import change_analyzer, posthoc, routing, story, telemetry, test_runner, workflow_runner

__all__ = [
    'change_analyzer', 'posthoc', 'routing', 'story', 'telemetry', 'test_runner', 'workflow_runner',
]
