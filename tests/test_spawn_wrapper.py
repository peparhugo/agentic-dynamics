"""Tests for the sibling-spawn wrapper (slice 2, proposal §2/D-14 + §5/D-16).

The load-bearing guarantee: a spawn request is validated against the scope model (the closed
five-scope vocabulary + the phase→scope authorization) and the mount contract (the four + the
D-2 auth set) BEFORE any docker/socket call. A validation bypass — a phase minting a container
with privileges it was never authorized for — is the FAILED finding this suite must catch.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from agentic_dynamics.experiment.experiment_spec import (
    SCOPE_VOCABULARY,
    phase_scope,
    validate_spec,
)
from scripts.fleet.spawn_wrapper import (
    AUTH_DIRS,
    COMMANDS_KEY,
    COMPOSE_ALLOWLIST,
    CONTRACT_TARGETS,
    FLEET_ACTIONS,
    MODEL_WHITELIST,
    SpawnValidationError,
    build_phase_request,
    build_spawn_argv,
    build_submit_argv,
    consume_fleet_commands,
    dispatch_submit,
    spawn_sibling,
    validate_fleet_command,
    validate_spawn,
    validate_submit_request,
)

# The canonical host repo path the mount contract's ``CONTRACT_TARGETS`` hardcodes for the
# repo-alias mounts (``spawn_wrapper.py``'s D-16 fix). ``build_phase_request`` derives that
# mount's target from ``FINOPS_REPO_DIR`` (default: wherever the checkout lives) — inside an
# isolated worktree (as tests run), that differs from the canonical path, so every submit test
# below pins ``FINOPS_REPO_DIR`` to the canonical value the contract expects (matching how the
# deployed ladder actually runs: the repo checked out at this fixed host path).
_CANONICAL_REPO_DIR = "/home/drseuss/ai-finops-framework"

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SUBMIT_SPEC = "workflows/repository/fleet_job_submission.yaml"


@pytest.fixture(autouse=False)
def _canonical_repo_env(monkeypatch):
    monkeypatch.setenv("FINOPS_REPO_DIR", _CANONICAL_REPO_DIR)


def _valid_submit_request(**overrides) -> dict:
    request = {
        "spec": _SUBMIT_SPEC,
        "goal": "make jobs submittable to the fleet",
        "model": "anthropic/claude-sonnet-5",
        "workdir": "/tmp/wt_test_submit_job",
    }
    request.update(overrides)
    return request

# A valid spawn request: p1_slice1_base_supervisor is authorized for "implementation"
# (the authorization table), the mounts are the full four + D-2 + the P0-3 per-attempt state
# namespace (/state rw) + the credential FILE mount (/auth/opencode_auth.json ro), results rw
# (implementation), the network is fleet-net, and the implementation scope authorizes the
# write flag.
VALID_REQUEST = {
    "phase": "p1_slice1_base_supervisor",
    "scope": "implementation",
    "mounts": [
        {"target": "/tmp", "mode": "rw"},
        {"target": "/app/experiments/results", "mode": "rw"},
        {"target": "/repo", "mode": "ro"},
        {"target": "/home/drseuss/.claude", "mode": "ro"},
        {"target": "/home/drseuss/.local/bin", "mode": "ro"},
        {"target": "/home/drseuss/.local/share/claude", "mode": "ro"},
        {"target": "/home/drseuss/.opencode/bin", "mode": "ro"},
        {"target": "/state", "mode": "rw"},
        {"target": "/auth/opencode_auth.json", "mode": "ro"},
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


# ── P0-3 — the per-attempt state namespace (control-plane stabilization) ──────


def test_state_target_is_in_the_contract_as_rw():
    """P0-3: /state is the ONE writable CLI-state namespace a cell may mount — the shared
    pool directory is never a valid mount target."""
    assert CONTRACT_TARGETS["/state"] == ("state", "rw")


def test_host_opencode_state_dir_is_out_of_contract():
    """P0-3: the host's LIVE opencode state directory must never enter a cell in ANY mode —
    the credential is a file mount, the writable state is the per-attempt namespace."""
    assert "/home/drseuss/.local/share/opencode" not in AUTH_DIRS
    assert CONTRACT_TARGETS.get("/home/drseuss/.local/share/opencode") is None


def test_credential_file_mount_is_in_the_contract_as_ro():
    assert CONTRACT_TARGETS["/auth/opencode_auth.json"] == ("auth-file", "ro")


def test_build_phase_request_mints_a_unique_state_namespace(tmp_path, _canonical_repo_env):
    """P0-3: every phase request carries its OWN writable state namespace at /state (rw) plus
    the XDG redirects, so two concurrent cells can never share a session DB. Two requests for
    the same phase share a namespace (the retry), two for different phases never do."""
    from scripts.fleet.spawn_wrapper import (
        STATE_ROOT,
        STATE_TARGET,
        build_phase_request,
        validate_spawn,
    )

    phase_a = {"name": "p1_slice1_base_supervisor", "kind": "agent", "scope": "implementation"}
    phase_b = {"name": "p2_slice1_workers_live", "kind": "agent", "scope": "implementation"}
    req_a = build_phase_request(phase_a, goal="g", workdir="/tmp/wt", model="m", spec_name="spec_x")
    req_b = build_phase_request(phase_b, goal="g", workdir="/tmp/wt", model="m", spec_name="spec_x")

    mounts_a = {m["target"]: m for m in req_a["mounts"]}
    mounts_b = {m["target"]: m for m in req_b["mounts"]}

    # Both carry the state mount (rw) and the credential file (ro)...
    assert mounts_a[STATE_TARGET]["mode"] == "rw"
    assert mounts_a["/auth/opencode_auth.json"]["mode"] == "ro"
    assert mounts_b[STATE_TARGET]["mode"] == "rw"

    # ...but they point at DIFFERENT host namespaces — never one shared pool directory.
    assert mounts_a[STATE_TARGET]["source"] != mounts_b[STATE_TARGET]["source"]
    assert str(Path(STATE_ROOT) / "spec_x" / "p1_slice1_base_supervisor") == mounts_a[STATE_TARGET]["source"]
    assert str(Path(STATE_ROOT) / "spec_x" / "p2_slice1_workers_live") == mounts_b[STATE_TARGET]["source"]

    # The XDG redirects land the CLI's writable state inside the per-attempt namespace.
    assert req_a["env"]["XDG_DATA_HOME"] == f"{STATE_TARGET}/data"
    assert req_a["env"]["XDG_CONFIG_HOME"] == f"{STATE_TARGET}/config"
    assert req_a["env"]["XDG_CACHE_HOME"] == f"{STATE_TARGET}/cache"

    # And a request assembled this way passes the full validation gate.
    request = {
        "phase": "p1_slice1_base_supervisor",
        "scope": "implementation",
        "mounts": req_a["mounts"],
        "network": "fleet-net",
        "env": req_a["env"],
    }
    assert validate_spawn(request) == []


def test_state_namespace_cannot_escape_the_state_root():
    """P0-3: a hostile state_namespace (.., absolute path) must be neutralized — it can never
    walk the state root to a shared or host directory."""
    from scripts.fleet.spawn_wrapper import _sanitize_namespace

    assert _sanitize_namespace("../../etc") == "etc"
    assert _sanitize_namespace("/abs/path") == "abs/path"
    assert _sanitize_namespace("..") == "unnamed"
    assert _sanitize_namespace("spec_x/phase 1") == "spec_x/phase 1"


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
    from agentic_dynamics.experiment.experiment_spec import load_spec

    yaml_path = tmp_path / "spec.yaml"
    yaml_path.write_text(
        "name: s\nquestion: q\nversion: '1'\nworkflow:\n  kind: agent_task\n"
        "  params:\n    phases:\n      - {name: p1, scope: review_readonly, prompt: hi}\n"
        "factors: []\ndesign: factorial\n"
    )
    spec = load_spec(yaml_path)
    assert phase_scope(spec.workflow.params["phases"][0]) == "review_readonly"


# ── the submit contract (p1_submit_contract) ──────────────────────────────────
#
# "submit" is a fourth member of the supervisor's command vocabulary alongside
# scale/drain/restart: fleet_manager submit -> fleet:commands -> the orchestrator's
# spawn-wrapper validates BEFORE any docker/socket call, exactly like every other action here.
# The load-bearing guarantee is the same one the rest of this file tests: a submit that names
# an unauthorized scope, an unlisted model, a host-service path, or an undeclared write flag
# never reaches build_submit_argv / a docker call.


def test_submit_is_in_the_fleet_action_vocabulary():
    assert "submit" in FLEET_ACTIONS


def test_model_whitelist_matches_the_seven_models_in_use():
    # AGENTS.md "Models in use" — the same seven the experiment matrix runs.
    expected = {
        "deepseek/deepseek-v4-flash",
        "deepseek/deepseek-v4-pro",
        "anthropic/claude-haiku-4-5",
        "anthropic/claude-sonnet-5",
        "openai/gpt-5.6-luna",
        "openai/gpt-5.6-sol",
        "openai/gpt-5.6-terra",
    }
    assert expected == MODEL_WHITELIST


# ── a valid submit passes ──────────────────────────────────────────────────────


def test_valid_submit_passes_validation(_canonical_repo_env):
    errors = validate_submit_request(_valid_submit_request())
    assert errors == []


def test_valid_submit_dispatch_builds_the_compose_run_argv(_canonical_repo_env):
    result = dispatch_submit(_valid_submit_request(), dry_run=True)
    assert result["ok"] is True
    argv = result["argv"]
    assert argv[:2] == ["docker-compose", "-f"]
    assert "run" in argv and "--rm" in argv and "workflow-runner" in argv
    assert "scripts/run_workflow.py" in argv
    assert "--orchestrator" in argv
    assert "--spec" in argv and _SUBMIT_SPEC in argv
    assert "--model" in argv and "anthropic/claude-sonnet-5" in argv


def test_build_submit_argv_is_the_reference_orchestrator_invocation():
    argv = build_submit_argv(
        {"job_id": "abc123", "spec": "workflows/repository/x.yaml", "goal": "g",
         "model": "anthropic/claude-sonnet-5", "workdir": "/tmp/wt_x"},
        compose="docker-compose", compose_file="/repo/infrastructure/docker-compose.ladder.yml",
    )
    joined = " ".join(argv)
    assert "docker-compose -f /repo/infrastructure/docker-compose.ladder.yml run --rm" in joined
    assert "FINOPS_CELL_ID=abc123" in joined
    assert "workflow-runner python3 scripts/run_workflow.py" in joined
    assert "--spec workflows/repository/x.yaml" in joined
    assert "--workdir /tmp/wt_x" in joined
    assert argv[-1] == "--orchestrator"


# ── spec resolution + compile-validation (step 1) ──────────────────────────────


def test_submit_missing_spec_fails():
    errors = validate_submit_request(_valid_submit_request(spec=""))
    assert any("spec path is required" in e for e in errors)


def test_submit_spec_path_escaping_repo_root_fails():
    errors = validate_submit_request(_valid_submit_request(spec="../etc/passwd"))
    assert any("escapes the repository root" in e for e in errors)


def test_submit_spec_outside_declared_spec_dirs_fails():
    # A real, resolvable, in-repo file — but not under workflows/ or experiments/definitions/.
    errors = validate_submit_request(_valid_submit_request(spec="AGENTS.md"))
    assert any("outside the declared spec directories" in e for e in errors)


def test_submit_spec_that_does_not_resolve_fails():
    errors = validate_submit_request(_valid_submit_request(spec="workflows/repository/does_not_exist.yaml"))
    assert any("does not resolve to a file" in e for e in errors)


def test_submit_spec_that_fails_compile_validation_is_refused(tmp_path, monkeypatch):
    # A spec with a phase declaring an undeclared scope fails validate_spec, so compile_spec
    # raises SpecError — validate_submit_request must surface that as a refusal, not a crash.
    bad_spec_dir = _REPO_ROOT / "workflows" / "repository"
    bad_spec_path = bad_spec_dir / "_test_submit_contract_bad_spec.yaml"
    bad_spec_path.write_text(
        "name: bad\nquestion: q\nversion: '1'\nworkflow:\n  kind: agent_task\n"
        "  params:\n    phases:\n      - {name: p1, scope: not_a_scope, prompt: hi}\n"
        "factors: []\ndesign: factorial\n"
    )
    try:
        errors = validate_submit_request(
            _valid_submit_request(spec="workflows/repository/_test_submit_contract_bad_spec.yaml")
        )
        assert any("does not compile-validate" in e for e in errors)
    finally:
        bad_spec_path.unlink(missing_ok=True)


# ── model whitelist (step 2) ────────────────────────────────────────────────────


def test_submit_model_outside_whitelist_fails(_canonical_repo_env):
    errors = validate_submit_request(_valid_submit_request(model="openai/gpt-6-hypothetical"))
    assert any("not in the model whitelist" in e for e in errors)


@pytest.mark.parametrize("model", sorted(MODEL_WHITELIST))
def test_every_whitelisted_model_passes_the_model_check(_canonical_repo_env, model):
    errors = validate_submit_request(_valid_submit_request(model=model))
    assert not any("model" in e and "whitelist" in e for e in errors)


# ── workdir: an allowed worktree path (step 3) — the isolation guard ───────────


def test_submit_missing_workdir_fails():
    errors = validate_submit_request(_valid_submit_request(workdir=""))
    assert any("workdir is required" in e for e in errors)


def test_submit_workdir_naming_the_story_redis_host_service_fails():
    # AGENTS.md: story agents build against finops-redis on 6379 — never the framework queue.
    # A submit request whose workdir names that host service must be refused pre-socket.
    errors = validate_submit_request(_valid_submit_request(workdir="127.0.0.1:6379"))
    assert any("names a host service" in e for e in errors)


def test_submit_workdir_naming_the_compose_hostname_fails():
    errors = validate_submit_request(_valid_submit_request(workdir="finops-redis:6379/db0"))
    assert any("names a host service" in e for e in errors)


def test_submit_workdir_outside_the_worktree_root_fails():
    errors = validate_submit_request(_valid_submit_request(workdir="/etc/passwd"))
    assert any("not a path strictly under the worktree root" in e for e in errors)


def test_submit_workdir_equal_to_the_worktree_root_itself_fails():
    errors = validate_submit_request(_valid_submit_request(workdir="/tmp"))
    assert any("not a path strictly under the worktree root" in e for e in errors)


# ── goal present (step 4) ───────────────────────────────────────────────────────


def test_submit_missing_goal_fails():
    errors = validate_submit_request(_valid_submit_request(goal=""))
    assert any("goal is required" in e for e in errors)


def test_submit_blank_goal_fails():
    errors = validate_submit_request(_valid_submit_request(goal="   "))
    assert any("goal is required" in e for e in errors)


# ── mounts derived from the phase scopes stay in the contract (step 5) ─────────
# — "a bad scope failing BEFORE any docker call" (VERIFY) —


def test_submit_with_an_unauthorized_phase_scope_fails_before_any_docker_call(
    tmp_path, monkeypatch, _canonical_repo_env
):
    # A phase with no declared scope and no PHASE_SCOPE_AUTHORIZATION entry resolves to an
    # empty scope (build_phase_request's own documented behavior) — validate_spawn refuses it
    # at its step 1/2, and validate_submit_request must surface that refusal.
    unauth_spec_dir = _REPO_ROOT / "workflows" / "repository"
    unauth_spec_path = unauth_spec_dir / "_test_submit_contract_unauthorized_scope.yaml"
    unauth_spec_path.write_text(
        "name: unauth\nquestion: q\nversion: '1'\nworkflow:\n  kind: agent_task\n"
        "  params:\n    phases:\n      - {name: p_never_registered_anywhere, prompt: hi}\n"
        "factors: []\ndesign: factorial\n"
    )
    try:
        request = _valid_submit_request(
            spec="workflows/repository/_test_submit_contract_unauthorized_scope.yaml"
        )
        errors = validate_submit_request(request)
        assert errors, "an unauthorized phase scope must be refused"
        assert any("p_never_registered_anywhere" in e for e in errors)

        # The socket guarantee: dispatch_submit must raise BEFORE building/running any argv.
        with pytest.raises(SpawnValidationError) as exc:
            dispatch_submit(request, dry_run=False)
        assert any("p_never_registered_anywhere" in e for e in exc.value.errors)
    finally:
        unauth_spec_path.unlink(missing_ok=True)


def test_submit_mount_derivation_reuses_the_step_3_mount_contract_check(_canonical_repo_env):
    # Every phase in the real submit-verb spec is scope: implementation — its derived mounts
    # (build_phase_request) must land squarely inside CONTRACT_TARGETS, the same four-mount +
    # D-2 auth set every other spawn is checked against.
    errors = validate_submit_request(_valid_submit_request())
    assert not any("step 3" in e for e in errors)


# ── network = fleet-net (step 6) ────────────────────────────────────────────────


def test_submit_network_mismatch_fails(_canonical_repo_env):
    errors = validate_submit_request(_valid_submit_request(network="ai-infra"))
    assert any("!= fleet-net" in e for e in errors)


def test_submit_default_network_is_fleet_net(_canonical_repo_env):
    # fleet_manager submit never sets --network; the default must be the permitted value.
    errors = validate_submit_request(_valid_submit_request())
    assert not any("fleet-net" in e for e in errors)


# ── write flags declared (step 7) — "an undeclared write flag failing" (VERIFY) ─


def test_submit_actuation_armed_is_always_refused(_canonical_repo_env):
    request = _valid_submit_request(env={"FINOPS_ACTUATION_ARMED": "1"})
    errors = validate_submit_request(request)
    assert any("FINOPS_ACTUATION_ARMED is never set" in e for e in errors)

    with pytest.raises(SpawnValidationError) as exc:
        dispatch_submit(request, dry_run=False)
    assert any("FINOPS_ACTUATION_ARMED" in e for e in exc.value.errors)


def test_submit_kb_write_undeclared_without_an_implementation_phase_fails(tmp_path, monkeypatch):
    # A research_readonly-only spec never authorizes FINOPS_KB_WRITE — a request smuggling it
    # in must be refused, independent of the mount-contract checks (isolated via a scope that
    # doesn't touch the /repo-alias mount, so this doesn't need _canonical_repo_env).
    ro_spec_dir = _REPO_ROOT / "workflows" / "repository"
    ro_spec_path = ro_spec_dir / "_test_submit_contract_research_only.yaml"
    ro_spec_path.write_text(
        "name: ro\nquestion: q\nversion: '1'\nworkflow:\n  kind: agent_task\n"
        "  params:\n    phases:\n      - {name: p1_research_infra, prompt: hi}\n"
        "factors: []\ndesign: factorial\n"
    )
    try:
        request = _valid_submit_request(
            spec="workflows/repository/_test_submit_contract_research_only.yaml",
            env={"FINOPS_KB_WRITE": "1"},
        )
        errors = validate_submit_request(request)
        assert any("FINOPS_KB_WRITE=1 is undeclared" in e for e in errors)
    finally:
        ro_spec_path.unlink(missing_ok=True)


# ── per-job image (step 8, p3_base_image_caching) ──────────────────────────────


def test_submit_without_image_passes(_canonical_repo_env):
    # image is optional — absent entirely is the common case (fleet_manager submit without
    # --image), and must not fail step 8.
    errors = validate_submit_request(_valid_submit_request())
    assert not any("image" in e for e in errors)


def test_submit_with_a_valid_job_image_passes(_canonical_repo_env):
    errors = validate_submit_request(_valid_submit_request(image="fleet/job-example"))
    assert errors == []


@pytest.mark.parametrize(
    "image",
    [
        "fleet/base",           # the ladder's own cache root — never a job's to pick directly
        "fleet/orchestrator",   # the one socket-holder's own image
        "fleet/supervisor",
        "fleet/job-",           # no name after the prefix
        "fleet/job-Bad-Name",   # uppercase — outside JOB_IMAGE_PATTERN
        "evil/attacker-image",  # a third-party image entirely
        "fleet/job-x; rm -rf /",  # shell-metacharacter smuggling attempt
    ],
)
def test_submit_image_outside_the_job_namespace_fails(_canonical_repo_env, image):
    errors = validate_submit_request(_valid_submit_request(image=image))
    assert any("fleet/job-<name>" in e for e in errors)


def test_build_submit_argv_carries_cell_image_when_present():
    argv = build_submit_argv(
        {"spec": "workflows/repository/x.yaml", "goal": "g",
         "model": "anthropic/claude-sonnet-5", "workdir": "/tmp/wt_x",
         "image": "fleet/job-example"},
    )
    assert "--cell-image" in argv
    assert argv[argv.index("--cell-image") + 1] == "fleet/job-example"
    assert argv[-2:] == ["--cell-image", "fleet/job-example"]


def test_build_submit_argv_omits_cell_image_when_absent():
    argv = build_submit_argv(
        {"spec": "workflows/repository/x.yaml", "goal": "g",
         "model": "anthropic/claude-sonnet-5", "workdir": "/tmp/wt_x"},
    )
    assert "--cell-image" not in argv
    assert argv[-1] == "--orchestrator"


def test_valid_submit_dispatch_with_image_reaches_the_compose_run_argv(_canonical_repo_env):
    result = dispatch_submit(_valid_submit_request(image="fleet/job-example"), dry_run=True)
    assert result["ok"] is True
    assert "--cell-image" in result["argv"]
    assert "fleet/job-example" in result["argv"]


# ── validate_fleet_command delegates "submit" whole (D-14 dispatch surface) ────


def test_validate_fleet_command_delegates_submit_to_validate_submit_request(_canonical_repo_env):
    assert validate_fleet_command(_valid_submit_request(action="submit")) == []


def test_validate_fleet_command_submit_does_not_require_a_service():
    # scale/drain/restart require "service" ∈ COMPOSE_ALLOWLIST; submit must not be checked
    # against that allowlist at all (it has no "service" field).
    request = _valid_submit_request(action="submit", spec="", model="", workdir="", goal="")
    errors = validate_fleet_command(request)
    assert not any("compose allowlist" in e for e in errors)


# ── consume_fleet_commands: the launch handler's board + DLQ wiring (p2_launch_handler) ────
#
# No docker/redis daemon is exercised here — the redis client is a fake, and `subprocess.run`
# is monkeypatched to a canned exit code, so these are "dry runs" in the same sense the rest of
# this module already uses the word (dispatch_submit(..., dry_run=True) never calls docker
# either): every OTHER step (validation, argv construction, board/DLQ writes) is the real code
# path. Deliberately never LPUSHes onto the live `fleet:commands` (db1/6380) the deployed
# ladder's own daemons are consuming — that queue is shared production state.


class _FakeCommandsRedis:
    """A minimal redis stand-in covering exactly the calls consume_fleet_commands makes."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = {}
        self._lists: dict[str, list[str]] = {}

    def lpush(self, key: str, value: str) -> int:
        self._lists.setdefault(key, []).insert(0, value)
        return len(self._lists[key])

    def brpop(self, key: str, timeout: int | None = None):
        lst = self._lists.get(key)
        if not lst:
            return None
        return key, lst.pop()

    def hset(self, key: str, mapping: dict | None = None, **_kw) -> None:
        self._hashes.setdefault(key, {}).update({k: str(v) for k, v in (mapping or {}).items()})

    def hget(self, key: str, field: str) -> str | None:
        return self._hashes.get(key, {}).get(field)

    def hvals(self, key: str) -> list[str]:
        return list(self._hashes.get(key, {}).values())

    def rpush(self, key: str, *values: str) -> int:
        self._lists.setdefault(key, []).extend(values)
        return len(self._lists[key])

    def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))

    def scan_iter(self, match: str | None = None, count: int | None = None):
        return iter([])

    def hgetall(self, key: str) -> dict[str, str]:
        return {}


# The committed dry-run fixture (workflows/repository/launch_handler_dry_run.yaml): a real,
# permanently-registered, single no-op-phase spec — "p_launch_handler_noop" is a genuine entry
# in PHASE_SCOPE_AUTHORIZATION (scope: implementation), so it is a job that ACTUALLY validates
# and launches, not a synthetic fixture that only proves a refusal.
_NOOP_SPEC_NAME = "launch_handler_dry_run"
_NOOP_SPEC_REL = "workflows/repository/launch_handler_dry_run.yaml"


def _push_submit(r: _FakeCommandsRedis, **overrides) -> dict:
    command = {
        "action": "submit",
        "job_id": "job-noop-1",
        "spec": _NOOP_SPEC_REL,
        "goal": "run the no-op phase",
        "model": "anthropic/claude-sonnet-5",
        "workdir": "/tmp/wt_launch_handler_test",
        "ts": 0.0,
        "nonce": "abc",
    }
    command.update(overrides)
    r.lpush(COMMANDS_KEY, json.dumps(command))
    return command


@pytest.fixture
def _noop_spec(_canonical_repo_env):
    ledger_dir = _REPO_ROOT / "experiments" / "results" / "workflows" / _NOOP_SPEC_NAME
    try:
        yield _REPO_ROOT / _NOOP_SPEC_REL, ledger_dir
    finally:
        if ledger_dir.is_dir():
            for f in ledger_dir.iterdir():
                f.unlink()
            ledger_dir.rmdir()


def _fleet_manager_module():
    import sys as _sys

    fleet_dir = str(_REPO_ROOT / "scripts" / "fleet")
    if fleet_dir not in _sys.path:
        _sys.path.insert(0, fleet_dir)
    import fleet_manager

    return fleet_manager


def test_consume_fleet_commands_valid_submit_reaches_running_then_completed_with_ledger(
    _noop_spec, monkeypatch,
):
    fleet_manager = _fleet_manager_module()
    spec_path, ledger_dir = _noop_spec
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_file = ledger_dir / "20260901T000000Z.json"
    ledger_file.write_text("{}")

    r = _FakeCommandsRedis()
    cmd = fleet_manager._send_submit_command(
        r, spec=_NOOP_SPEC_REL, goal="run the no-op phase",
        model="anthropic/claude-sonnet-5", workdir="/tmp/wt_launch_handler_test",
    )
    assert fleet_manager.build_board(r)["jobs"][0]["status"] == "launching"

    calls = []

    def fake_run(argv, check=False):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    consume_fleet_commands(client=r, once=True)

    assert len(calls) == 1
    assert "--orchestrator" in calls[0] and "workflow-runner" in calls[0]

    job = fleet_manager.build_board(r)["jobs"][0]
    assert job["job_id"] == cmd["job_id"]
    assert job["spec"] == _NOOP_SPEC_REL
    assert job["model"] == "anthropic/claude-sonnet-5"
    assert job["status"] == "completed"
    assert job["returncode"] == 0
    assert job["ledger"] == str(ledger_file)


def test_consume_fleet_commands_nonzero_exit_marks_failed_and_files_the_dlq(
    _noop_spec, monkeypatch,
):
    fleet_manager = _fleet_manager_module()
    r = _FakeCommandsRedis()
    cmd = fleet_manager._send_submit_command(
        r, spec=_NOOP_SPEC_REL, goal="run the no-op phase",
        model="deepseek/deepseek-v4-pro", workdir="/tmp/wt_launch_handler_test",
    )

    monkeypatch.setattr(
        subprocess, "run",
        lambda argv, check=False: subprocess.CompletedProcess(argv, returncode=1),
    )

    consume_fleet_commands(client=r, once=True)

    job = fleet_manager.build_board(r)["jobs"][0]
    assert job["job_id"] == cmd["job_id"]
    assert job["status"] == "failed"
    assert job["returncode"] == 1

    dead = [json.loads(e) for e in r._lists.get("fleet_jobs:dead_letter", [])]
    assert len(dead) == 1
    assert dead[0]["job"]["job_id"] == cmd["job_id"]
    assert "exited 1" in dead[0]["reason"]


def test_consume_fleet_commands_invalid_submit_is_refused_before_any_subprocess_call(
    _noop_spec, monkeypatch,
):
    # A deliberately invalid submit (a workdir naming the story-agent Redis host service) —
    # refused at validate_fleet_command, BEFORE any docker/compose subprocess call. The board
    # goes straight to "failed" (never leaving a phantom "launching" record) and a DLQ entry
    # is filed even though the socket was never reached.
    r = _FakeCommandsRedis()
    fleet_manager = _fleet_manager_module()
    cmd = fleet_manager._send_submit_command(
        r, spec=_NOOP_SPEC_REL, goal="run the no-op phase",
        model="anthropic/claude-sonnet-5", workdir="127.0.0.1:6379",
    )

    calls = []
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: calls.append(a) or subprocess.CompletedProcess(a, 0),
    )

    consume_fleet_commands(client=r, once=True)

    assert calls == []
    job = fleet_manager.build_board(r)["jobs"][0]
    assert job["job_id"] == cmd["job_id"]
    assert job["status"] == "failed"
    assert "host service" in job["error"]

    dead = [json.loads(e) for e in r._lists.get("fleet_jobs:dead_letter", [])]
    assert len(dead) == 1
    assert dead[0]["job"]["job_id"] == cmd["job_id"]


def test_consume_fleet_commands_dry_run_never_calls_subprocess(_noop_spec, monkeypatch):
    r = _FakeCommandsRedis()
    fleet_manager = _fleet_manager_module()
    fleet_manager._send_submit_command(
        r, spec=_NOOP_SPEC_REL, goal="run the no-op phase",
        model="anthropic/claude-sonnet-5", workdir="/tmp/wt_launch_handler_test",
    )

    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a))

    consume_fleet_commands(client=r, once=True, dry_run=True)

    assert calls == []
    # dry_run never observes an exit code, so the record stops at "running" — never a
    # fabricated completed/failed.
    job = fleet_manager.build_board(r)["jobs"][0]
    assert job["status"] == "running"
