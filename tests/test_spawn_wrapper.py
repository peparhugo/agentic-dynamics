"""Tests for the sibling-spawn wrapper (slice 2, proposal §2/D-14 + §5/D-16).

The load-bearing guarantee: a spawn request is validated against the scope model (the closed
five-scope vocabulary + the phase→scope authorization) and the mount contract (the four + the
D-2 auth set) BEFORE any docker/socket call. A validation bypass — a phase minting a container
with privileges it was never authorized for — is the FAILED finding this suite must catch.
"""

from __future__ import annotations

import pytest

from agentic_dynamics.experiment.experiment_spec import (
    PHASE_SCOPE_AUTHORIZATION,
    SCOPE_VOCABULARY,
    phase_scope,
    validate_spec,
)
from scripts.fleet.spawn_wrapper import (
    COMPOSE_ALLOWLIST,
    CONTRACT_TARGETS,
    SpawnValidationError,
    build_phase_request,
    build_spawn_argv,
    spawn_sibling,
    validate_fleet_command,
    validate_spawn,
)

# A valid spawn request: p1_slice1_base_supervisor is authorized for "implementation"
# (the authorization table), the mounts are the full four + D-2, results rw (implementation),
# the network is fleet-net, and the implementation scope authorizes the write flag.
VALID_REQUEST = {
    "phase": "p1_slice1_base_supervisor",
    "scope": "implementation",
    "mounts": [
        {"target": "/tmp", "mode": "rw"},
        {"target": "/app/experiments/results", "mode": "rw"},
        {"target": "/repo", "mode": "ro"},
        {"target": "/home/drseuss/.claude", "mode": "ro"},
        {"target": "/home/drseuss/.local/share/opencode", "mode": "ro"},
        {"target": "/home/drseuss/.local/bin", "mode": "ro"},
        {"target": "/home/drseuss/.local/share/claude", "mode": "ro"},
        {"target": "/home/drseuss/.opencode/bin", "mode": "ro"},
    ],
    "network": "fleet-net",
    "env": {"FINOPS_KB_WRITE": "1"},
}


# ── step 1 — scope membership ────────────────────────────────────────────────


def test_scope_not_in_vocabulary_fails_step_1():
    request = {**VALID_REQUEST, "scope": "admin_everything"}
    errors = validate_spawn(request)
    assert errors and any("step 1" in e and "vocabulary" in e for e in errors)


def test_every_vocabulary_member_is_accepted_at_step_1():
    for scope in SCOPE_VOCABULARY:
        errors = validate_spawn({**VALID_REQUEST, "scope": scope})
        # step 2 may reject (the phase is only authorized for "implementation"); step 1 must not.
        assert not any(e.startswith("step 1") for e in errors), f"step 1 rejected {scope!r}"


# ── step 2 — phase→scope authorization ───────────────────────────────────────


def test_unauthorized_scope_fails_step_2():
    # p6_adversarial is authorized for "adversarial_readonly" (the table); requesting
    # "implementation" must fail at step 2, before any mount/env check.
    request = {**VALID_REQUEST, "phase": "p6_adversarial", "scope": "implementation"}
    errors = validate_spawn(request)
    assert errors and any("step 2" in e and "not authorized" in e for e in errors)


def test_declared_scope_overrides_the_table():
    # A phase that DECLARES implementation (via phase_scopes) is authorized for it even when
    # the table says otherwise.
    errors = validate_spawn(
        {**VALID_REQUEST, "phase": "p6_adversarial", "scope": "implementation"},
        phase_scopes={"p6_adversarial": "implementation"},
    )
    assert errors == []


def test_unknown_phase_is_unauthorized():
    # A phase with no table entry and no declared scope is authorized for nothing.
    errors = validate_spawn({**VALID_REQUEST, "phase": "p9_unknown", "scope": "implementation"})
    assert errors and any("step 2" in e for e in errors)


# ── step 3 — the mount contract ──────────────────────────────────────────────


def test_bad_mount_target_fails_step_3():
    request = {
        **VALID_REQUEST,
        "mounts": VALID_REQUEST["mounts"] + [{"target": "/etc/passwd", "mode": "ro"}],
    }
    errors = validate_spawn(request)
    assert errors and any("step 3" in e and "outside the four-mount contract" in e for e in errors)


def test_results_mount_mode_must_match_scope():
    # research_readonly declares results ro; a rw results mount must fail step 3.
    request = {
        **VALID_REQUEST,
        "phase": "p1_research_infra",
        "scope": "research_readonly",
        "mounts": [
            {"target": "/tmp", "mode": "rw"},
            {"target": "/app/experiments/results", "mode": "rw"},  # wrong: should be ro
            {"target": "/repo", "mode": "ro"},
        ],
        "network": "fleet-net",
        "env": {},
    }
    errors = validate_spawn(request)
    assert errors and any("step 3" in e and "results_mode" in e for e in errors)


def test_worktree_mount_must_be_rw():
    request = {
        **VALID_REQUEST,
        "mounts": [
            {"target": "/tmp", "mode": "ro"},  # wrong: worktree is rw
            {"target": "/app/experiments/results", "mode": "rw"},
            {"target": "/repo", "mode": "ro"},
        ],
    }
    errors = validate_spawn(request)
    assert errors and any("step 3" in e and "/tmp" in e for e in errors)


# ── step 4 + step 5 — network + env ──────────────────────────────────────────


def test_network_mismatch_fails_step_4():
    errors = validate_spawn({**VALID_REQUEST, "network": "ai-infra"})
    assert errors and any("step 4" in e for e in errors)


def test_undeclared_write_flag_fails_step_5():
    # review_readonly's write_flag is False — FINOPS_KB_WRITE=1 must be refused.
    request = {
        **VALID_REQUEST,
        "phase": "p3_review",
        "scope": "review_readonly",
        "mounts": [
            {"target": "/tmp", "mode": "rw"},
            {"target": "/app/experiments/results", "mode": "rw"},
            {"target": "/repo", "mode": "ro"},
        ],
        "env": {"FINOPS_KB_WRITE": "1"},
    }
    errors = validate_spawn(request)
    assert errors and any("step 5" in e and "FINOPS_KB_WRITE" in e for e in errors)


def test_actuation_armed_never_allowed():
    errors = validate_spawn({**VALID_REQUEST, "env": {"FINOPS_ACTUATION_ARMED": "1"}})
    assert errors and any("step 5" in e and "ACTUATION_ARMED" in e for e in errors)


def test_valid_request_passes():
    assert validate_spawn(VALID_REQUEST) == []


# ── the socket is never reached on a validation failure ──────────────────────


def test_spawn_sibling_refuses_before_socket_call():
    # A request failing step 1 raises SpawnValidationError and NEVER builds/executes a docker
    # argv — even with a docker binary path that would fail if invoked.
    with pytest.raises(SpawnValidationError) as exc:
        spawn_sibling(
            {**VALID_REQUEST, "scope": "admin_everything"},
            docker="/nonexistent/docker-should-never-run",
        )
    assert any("step 1" in e for e in exc.value.errors)


def test_spawn_sibling_dry_run_builds_argv_only_after_validation():
    result = spawn_sibling(VALID_REQUEST, docker="docker", dry_run=True)
    assert result["ok"] is True
    assert result["argv"][0] == "docker" and "run" in result["argv"]
    assert result["returncode"] is None


def test_build_spawn_argv_carries_mounts_network_env():
    argv = build_spawn_argv(VALID_REQUEST, docker="docker", image="fleet/base", command=["echo", "hi"])
    joined = "\n".join(argv)
    assert "--network" in argv and "fleet-net" in argv
    assert "/tmp:rw" in joined  # the worktree mount, rw
    assert "/repo:ro" in joined  # the repo mount, ro
    assert "FINOPS_KB_WRITE=1" in joined  # the implementation scope's write flag
    assert argv[-2:] == ["echo", "hi"]


# ── the fleet:commands validation (D-14) ─────────────────────────────────────


def test_fleet_command_scale_valid():
    assert validate_fleet_command({"action": "scale", "service": "story-worker", "count": 4}) == []


def test_fleet_command_unknown_service_refused():
    errors = validate_fleet_command({"action": "scale", "service": "postgres", "count": 2})
    assert any("not in the compose allowlist" in e for e in errors)


def test_fleet_command_unbounded_count_refused():
    errors = validate_fleet_command({"action": "scale", "service": "story-worker", "count": 9999})
    assert any("not an int in" in e for e in errors)


def test_fleet_command_unknown_action_refused():
    errors = validate_fleet_command({"action": "rm", "service": "story-worker"})
    assert any("is not one of" in e for e in errors)


def test_fleet_command_drain_and_restart_valid():
    assert validate_fleet_command({"action": "drain", "service": "analysis-worker"}) == []
    assert validate_fleet_command(
        {"action": "restart", "service": "fleet-manager", "backoff": 5}
    ) == []


def test_compose_allowlist_covers_the_ladder_services():
    # The allowlist must name the cell + supervisor + orchestrator services (the audit surface
    # for "the socket only touches these").
    for svc in ("story-worker", "analysis-worker", "review-unit", "fleet-manager",
                "control-room", "trigger-reviews", "campaign-wrapper", "workflow-runner",
                "kb-neo4j", "orphan-sweep", "egress"):
        assert svc in COMPOSE_ALLOWLIST, f"{svc!r} missing from the compose allowlist"


# ── build_phase_request — the campaign-wrapper mechanism (D-16) ───────────────


def test_build_phase_request_resolves_scope_and_results_mode():
    req = build_phase_request(
        {"name": "p1_research_infra"},
        goal="g", workdir="/tmp/wt", model="deepseek/deepseek-v4-pro",
    )
    assert req["scope"] == "research_readonly"
    results = [m for m in req["mounts"] if m["target"] == "/app/experiments/results"][0]
    assert results["mode"] == "ro"  # research_readonly narrows results to ro
    assert req["network"] == "fleet-net"
    assert "FINOPS_KB_WRITE" not in req["env"]


def test_build_phase_request_implementation_may_emit():
    req = build_phase_request(
        {"name": "p1_slice1_base_supervisor"},
        goal="g", workdir="/tmp/wt", model="deepseek/deepseek-v4-pro",
    )
    assert req["scope"] == "implementation"
    results = [m for m in req["mounts"] if m["target"] == "/app/experiments/results"][0]
    assert results["mode"] == "rw"
    assert req["env"]["FINOPS_KB_WRITE"] == "1"


def test_build_phase_request_without_authorization_yields_empty_scope():
    req = build_phase_request(
        {"name": "p_undeclared"},
        goal="g", workdir="/tmp/wt", model="deepseek/deepseek-v4-pro",
    )
    assert req["scope"] == ""  # no declared scope + no table entry → spawn will fail at step 2


# ── the scope field + authorization table (experiment_spec) ──────────────────


def test_phase_scope_declared_wins_over_table():
    assert phase_scope({"name": "p6_adversarial", "scope": "implementation"}) == "implementation"


def test_phase_scope_table_fallback():
    assert phase_scope({"name": "p6_adversarial"}) == "adversarial_readonly"
    assert phase_scope({"name": "p3_slice2_orchestrator"}) == "implementation"


def test_phase_scope_unknown_is_none():
    assert phase_scope({"name": "p_unknown"}) is None


def test_scope_field_bogus_fails_validation():
    from agentic_dynamics.experiment.experiment_spec import ExperimentSpec, Workflow

    spec = ExperimentSpec(
        name="s", question="q", version="1", design="factorial", factors=[],
        workflow=Workflow.from_dict({"kind": "agent_task", "params": {"phases": [
            {"name": "p1", "scope": "not_a_scope", "prompt": "hi"},
        ]}}),
    )
    errors = validate_spec(spec)
    assert any("scope" in e and "not_a_scope" in e for e in errors)


def test_scope_field_valid_member_validates_clean():
    from agentic_dynamics.experiment.experiment_spec import ExperimentSpec, Workflow

    spec = ExperimentSpec(
        name="s", question="q", version="1", design="factorial", factors=[],
        workflow=Workflow.from_dict({"kind": "agent_task", "params": {"phases": [
            {"name": "p1", "scope": "implementation", "prompt": "hi"},
            {"name": "p2", "scope": "adversarial_readonly", "prompt": "hi"},
        ]}}),
    )
    assert validate_spec(spec) == []


def test_scope_field_round_trips_through_yaml(tmp_path):
    from agentic_dynamics.experiment.experiment_spec import ExperimentSpec, load_spec

    yaml_path = tmp_path / "spec.yaml"
    yaml_path.write_text(
        "name: s\nquestion: q\nversion: '1'\nworkflow:\n  kind: agent_task\n"
        "  params:\n    phases:\n      - {name: p1, scope: review_readonly, prompt: hi}\n"
        "factors: []\ndesign: factorial\n"
    )
    spec = load_spec(yaml_path)
    assert phase_scope(spec.workflow.params["phases"][0]) == "review_readonly"
