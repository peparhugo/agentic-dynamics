"""Step 3a: the Docker executor's state namespace is per-RUN, not merely per-spec/phase.

The pre-step-3 ``<spec>/<phase>`` key let two runs of the same spec share one writable
CLI-state directory. With a run clone the namespace now carries the run id
(``runs_root/<run-id>/repo``); without a clone (the legacy shared-worktree shape) it keeps the
old form and fabricates no id.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _path in (_REPO_ROOT, _REPO_ROOT / "src", _REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "fleet"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from docker_executor import DockerAgentExecutor  # noqa: E402

from agentic_dynamics.runtime.executor import StepRequest  # noqa: E402


def _executor(**kwargs) -> DockerAgentExecutor:
    base = dict(
        spec_path="/repo/workflows/repository/t.yaml",
        spec_name="t",
        goal="g",
        model="m",
        workdir="/tmp/wt",
    )
    base.update(kwargs)
    return DockerAgentExecutor(**base)


def _request() -> StepRequest:
    return StepRequest(
        phase_name="p1",
        phase_kind="agent",
        prompt="do the thing",
        model="m",
        goal="g",
        spec_name="t",
        workdir="/tmp/wt",
        phase_def={"scope": "implementation"},
    )


def test_namespace_carries_the_run_id_when_a_clone_is_present():
    executor = _executor(run_clone="/tmp/runs/run-abc/repo")
    built = executor.build_request(_request())
    assert built["state_namespace"] == "t/run-abc/p1"


def test_namespace_keeps_the_legacy_shape_without_a_clone():
    executor = _executor()
    built = executor.build_request(_request())
    assert built["state_namespace"] == "t/p1"
