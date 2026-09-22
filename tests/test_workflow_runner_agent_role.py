"""L29 step 2: the ``run_agent`` phase key — the pure resolution the engine threads.

Precedence: the phase's ``run_agent`` > the workflow's ``agent`` param > the run's
``--agent`` default. EMPTY everywhere means "no role declared": the adapter keeps its
ordinary-worker pin, so a spec without the key behaves exactly as before.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agentic_dynamics.runtime.executor import StepRequest  # noqa: E402
from agentic_dynamics.runtime.workflow_runner import resolve_phase_agent  # noqa: E402


def test_the_phase_role_outranks_the_workflow_param_and_the_default():
    assert (
        resolve_phase_agent(
            {"run_agent": "adversarial-reviewer"}, {"agent": "site-editor"}, default="spec-author"
        )
        == "adversarial-reviewer"
    )
    assert (
        resolve_phase_agent({}, {"agent": "site-editor"}, default="spec-author") == "site-editor"
    )
    assert resolve_phase_agent({}, {}, default="spec-author") == "spec-author"


def test_no_declaration_means_no_role_never_an_invented_one():
    """The pin the adapter owns (WORKER_AGENT) is the absence case: "" — resolution must not
    guess a role for a spec that never asked for one."""
    assert resolve_phase_agent({}, {}) == ""
    assert resolve_phase_agent({"run_agent": "   "}, {"agent": ""}, default="") == ""
    assert resolve_phase_agent(None, None, default="") == ""
    assert resolve_phase_agent("not-a-mapping", 42, default="") == ""


def test_the_step_request_carries_the_resolved_role():
    request = StepRequest(
        phase_name="execute",
        phase_kind="agent",
        prompt="p",
        model="deepseek/deepseek-v4-flash",
        goal="g",
        spec_name="s",
        workdir="/tmp/w",
        agent="control-room-dev",
    )
    assert request.agent == "control-room-dev"
    assert StepRequest(
        phase_name="execute",
        phase_kind="agent",
        prompt="p",
        model="m",
        goal="g",
        spec_name="s",
        workdir="/tmp/w",
    ).agent == ""
