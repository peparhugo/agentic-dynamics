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

from agentic_dynamics.core.paths import PathConfig
from agentic_dynamics.experiment.experiment_spec import (
    SCOPE_VOCABULARY,
    load_spec,
    phase_scope,
    validate_spec,
)
from agentic_dynamics.runtime.executor import StepResult
from scripts.fleet.launch_broker import (
    build_launch_argv,
    build_submit_argv,
    container_view_config,
)
from scripts.fleet.spawn_wrapper import (
    AUTH_CRED_FILE,
    AUTH_DIRS,
    COMMANDS_KEY,
    COMPOSE_ALLOWLIST,
    CONTRACT_TARGETS,
    FLEET_ACTIONS,
    MODEL_WHITELIST,
    STATE_TARGET,
    SpawnValidationError,
    build_phase_request,
    build_verifier_request,
    consume_fleet_commands,
    contract_targets,
    dispatch_submit,
    spawn_sibling,
    validate_fleet_command,
    validate_spawn,
    validate_submit_request,
)

# The repo-alias contract (b1_path_config): the repo's host path is the config's
# ``repo_root``/``git_dir`` — derived from the env (``FINOPS_REPO_DIR``) with the package root
# as the default, never a host-specific literal. The wrapper's request builders and the
# validator derive the SAME values from the SAME config, so the spawn-contract tests assert
# against ``PathConfig`` values (the default config — wherever this checkout lives), not a
# pinned host path. ``build_phase_request`` derives the alias mount targets from the
# config; validation (step 3) accepts exactly those derived targets.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SUBMIT_SPEC = "workflows/repository/fleet_job_submission.yaml"


def _default_cfg() -> PathConfig:
    """The wrapper's default PathConfig (env-derived; no host literal)."""
    return PathConfig.from_env()


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
# write flag. The D-2 auth targets are the default config's ``auth_dirs`` (b1_path_config:
# derived, never host literals) — the same config validation derives its contract from.
# b3_launch_broker: the request also carries the TYPED launch fields (image_digest /
# mount_profile / state_namespace / timeout_seconds; command is added per test where the
# broker path is exercised) so it satisfies the broker's closed typed contract as well as the
# wrapper's scope checks.
VALID_REQUEST = {
    "phase": "p1_slice1_base_supervisor",
    "scope": "implementation",
    "mounts": [
        {"target": "/tmp", "mode": "rw"},
        {"target": "/app/experiments/results", "mode": "rw"},
        {"target": "/repo", "mode": "ro"},
        *[{"target": str(d), "mode": "ro"} for d in _default_cfg().auth_dirs],
        {"target": "/state", "mode": "rw"},
        {"target": "/auth/opencode_auth.json", "mode": "ro"},
    ],
    "network": "fleet-net",
    "env": {"FINOPS_KB_WRITE": "1"},
    "image_digest": "fleet/base",
    "mount_profile": "implementation_rw",
    "state_namespace": "spec_x/p1_slice1_base_supervisor",
    "timeout_seconds": 0,
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
    cfg = _default_cfg()
    live_state_dir = str(cfg.auth_home / ".local/share/opencode")
    assert live_state_dir not in AUTH_DIRS
    assert CONTRACT_TARGETS.get(live_state_dir) is None


def test_credential_file_mount_is_in_the_contract_as_ro():
    assert CONTRACT_TARGETS["/auth/opencode_auth.json"] == ("auth-file", "ro")


def test_build_phase_request_mints_a_unique_state_namespace(tmp_path):
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
    # A request failing step 1 raises SpawnValidationError and NEVER reaches the broker — even
    # with a docker path that would fail if invoked (the broker is never called).
    with pytest.raises(SpawnValidationError) as exc:
        spawn_sibling(
            {**VALID_REQUEST, "scope": "admin_everything"},
        )
    assert any("step 1" in e for e in exc.value.errors)


def test_spawn_sibling_dry_run_builds_the_broker_argv_only_after_validation(broker_seam):
    # fb2_broker_hostside: spawn_sibling validates, then emits the typed request to the host
    # broker OVER THE SEAM, which builds the docker argv (dry_run builds it only, nothing is
    # executed).
    request = {**VALID_REQUEST, "command": ["python3", "-c", "pass"]}
    result = spawn_sibling(request, dry_run=True)
    assert result["ok"] is True
    assert result["argv"][0] == "docker" and "run" in result["argv"]
    assert result["returncode"] is None


def test_broker_launch_argv_carries_mounts_network_env():
    # The docker argv construction now lives in the launch broker (the ONLY docker caller):
    # build_launch_argv assembles the -v mounts / --network / -e / image / command from a
    # validated request. The wrapper no longer builds docker argv.
    request = {**VALID_REQUEST, "command": ["echo", "hi"]}
    mounts = build_phase_request(
        {"name": "p1_slice1_base_supervisor", "scope": "implementation"},
        goal="g", workdir="/tmp/wt", model="m", spec_name="spec_x",
    )["mounts"]
    argv = build_launch_argv(request, docker="docker", mounts=mounts)
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


def _make_config_repo(tmp_path) -> tuple[Path, PathConfig]:
    """Scaffold a real repo root under ``tmp_path`` and the PathConfig pointing at it."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "experiments" / "results").mkdir(parents=True)
    auth = tmp_path / "auth"
    (auth / ".local" / "share" / "opencode").mkdir(parents=True)
    cfg = PathConfig(
        repo_root=repo,
        git_dir=repo / ".git",
        worktrees_root=tmp_path / "worktrees",
        runs_root=tmp_path / "runs",
        results_dir=repo / "experiments" / "results",
        state_root=tmp_path / "state",
        auth_home=auth,
    )
    return repo, cfg


def test_build_phase_request_resolves_mounts_to_the_configured_paths(tmp_path):
    """(b1 VERIFY c) the request's mounts resolve to the PathConfig's configured paths — never
    a host literal. A request built against an explicit config mounts THAT config's repo_root /
    git_dir / results_dir / worktrees_root / state_root / auth_home, and validates clean under
    the SAME config (the validator derives the identical contract)."""
    repo, cfg = _make_config_repo(tmp_path)
    req = build_phase_request(
        {"name": "p1_slice1_base_supervisor", "scope": "implementation"},
        goal="g", workdir="/tmp/wt", model="deepseek/deepseek-v4-pro",
        spec_name="spec_x", path_config=cfg,
    )
    by_target = {m["target"]: m for m in req["mounts"]}

    # the four-mount sources are the configured paths, never literals
    assert by_target["/tmp"]["source"] == str(cfg.worktrees_root)
    assert by_target["/app/experiments/results"]["source"] == str(cfg.results_dir)
    assert by_target["/repo"]["source"] == str(cfg.repo_root)
    assert by_target["/repo/.git"]["source"] == str(cfg.git_dir)
    # the D-16 host-path repo alias + its .git resolve to the configured repo_root/git_dir
    assert by_target[str(cfg.repo_root)] == {"source": str(cfg.repo_root),
                                             "target": str(cfg.repo_root), "mode": "ro"}
    assert by_target[str(cfg.git_dir)]["mode"] == "rw"
    # the D-2 auth set + the credential file derive from the configured auth_home
    auth_targets = {str(d) for d in cfg.auth_dirs}
    assert auth_targets <= set(by_target)
    cred = by_target["/auth/opencode_auth.json"]
    assert cred["source"] == str(cfg.auth_home / ".local/share/opencode/auth.json")
    # the per-attempt state namespace lives under the configured state_root
    assert by_target["/state"]["source"].startswith(str(cfg.state_root))
    # no host literal anywhere on the request
    joined = json.dumps(req)
    assert "/home/" not in joined and "ai-finops-framework" not in joined
    # and the request validates clean under the SAME config — contract and builder agree
    assert validate_spawn(
        req, phase_scopes={"p1_slice1_base_supervisor": "implementation"}, path_config=cfg,
    ) == []


def test_build_phase_request_stamps_the_view_of_the_config_it_built_against(tmp_path):
    """(ws2 VERIFY, builder half) every builder-made request carries the VIEW of the PathConfig
    its mounts were built against: host for a checkout-rooted config, container for a config
    rooted at the image's /app (the container-tier derivation). The broker validates the request
    against that view, so the builder and the broker can never disagree about which repo-alias
    targets are in contract."""
    _repo, cfg = _make_config_repo(tmp_path)
    host_req = build_phase_request(
        {"name": "p1_slice1_base_supervisor", "scope": "implementation"},
        goal="g", workdir="/tmp/wt", model="deepseek/deepseek-v4-pro",
        spec_name="spec_x", path_config=cfg,
    )
    assert host_req["view"] == "host"
    # the container view of the SAME host config re-roots the repo to the /app-in-container path
    container_cfg = container_view_config(cfg)
    assert str(container_cfg.repo_root) == "/app"
    container_req = build_phase_request(
        {"name": "p1_slice1_base_supervisor", "scope": "implementation"},
        goal="g", workdir="/tmp/wt", model="deepseek/deepseek-v4-pro",
        spec_name="spec_x", path_config=container_cfg,
    )
    assert container_req["view"] == "container"
    # its alias targets are the /app paths; validating under the SAME (container) config passes,
    # so the request is coherent with the view it declares.
    alias_targets = {m["target"] for m in container_req["mounts"]} & {"/app", "/app/.git"}
    assert alias_targets == {"/app", "/app/.git"}
    assert validate_spawn(
        container_req,
        phase_scopes={"p1_slice1_base_supervisor": "implementation"},
        path_config=container_cfg,
    ) == []
    # a verifier request built against the container config carries the container view too
    verifier_req = build_verifier_request(
        {"name": "g3_test_gate", "kind": "test", "scope": "implementation",
         "tests": ["tests/test_spec_x.py"]},
        goal="g", workdir="/tmp/wt_x", model="deepseek/deepseek-v4-flash",
        spec_name="spec_x", path_config=container_cfg,
    )
    assert verifier_req["view"] == "container"


def test_verifier_request_uses_the_configured_paths(tmp_path):
    """(b1 VERIFY c) the verifier's candidate surface (worktree /tmp, /repo, both git dirs)
    resolves to the CONFIGURED paths too — the config is threaded through both request
    builders, never a literal."""
    _repo, cfg = _make_config_repo(tmp_path)
    req = build_verifier_request(
        {"name": "g3_test_gate", "kind": "test", "scope": "implementation",
         "tests": ["tests/test_spec_x.py"]},
        goal="g", workdir="/tmp/wt_x", model="deepseek/deepseek-v4-flash",
        spec_name="spec_x", path_config=cfg,
    )
    by_target = {m["target"]: m for m in req["mounts"]}
    assert by_target[str(cfg.git_dir)]["mode"] == "ro"  # read-only candidate
    auth_targets = {str(d) for d in cfg.auth_dirs}
    assert not (set(by_target) & auth_targets)  # verifier carries no credential surface
    assert validate_spawn(
        req, phase_scopes={"g3_test_gate": "implementation"}, path_config=cfg,
    ) == []


def test_phase_request_references_the_run_clone_path(tmp_path):
    """(b2 VERIFY d) the executor's phase request references the run's private clone path.

    ``build_phase_request(run_clone=<path>)`` stamps the clone path on the request as a
    top-level reference — the launch broker (b3) binds its mount profile to it. It is NOT a
    mount (the four-mount + D-2 contract is unchanged), so the request still validates clean
    under the SAME config. Omitted (the default), the request carries no clone key."""
    repo, cfg = _make_config_repo(tmp_path)
    clone_path = cfg.runs_root / "run-abc" / "repo"

    req = build_phase_request(
        {"name": "p1_slice1_base_supervisor", "scope": "implementation"},
        goal="g", workdir="/tmp/wt", model="deepseek/deepseek-v4-pro",
        spec_name="spec_x", path_config=cfg, run_clone=clone_path,
    )
    assert req["run_clone"] == str(clone_path)
    # a request carrying the clone path still validates under the same contract
    assert validate_spawn(
        req, phase_scopes={"p1_slice1_base_supervisor": "implementation"}, path_config=cfg,
    ) == []

    bare = build_phase_request(
        {"name": "p1_slice1_base_supervisor", "scope": "implementation"},
        goal="g", workdir="/tmp/wt", model="deepseek/deepseek-v4-pro",
        spec_name="spec_x", path_config=cfg,
    )
    assert "run_clone" not in bare


def test_verifier_request_references_the_run_clone_path(tmp_path):
    """(b2 VERIFY d) the verifier request references the run clone too — a test phase verifies
    against the run's read-only clone. The reference survives the forbidden-surface drop (it
    is not a mount), and the verifier request still validates clean."""
    _repo, cfg = _make_config_repo(tmp_path)
    clone_path = cfg.runs_root / "run-abc" / "repo"

    req = build_verifier_request(
        {"name": "g3_test_gate", "kind": "test", "scope": "implementation",
         "tests": ["tests/test_spec_x.py"]},
        goal="g", workdir="/tmp/wt_x", model="deepseek/deepseek-v4-flash",
        spec_name="spec_x", path_config=cfg, run_clone=clone_path,
    )
    assert req["run_clone"] == str(clone_path)
    # the verifier's read-only-for-candidate contract is intact alongside the reference
    assert all(m.get("mode") == "ro" for m in req["mounts"])
    assert validate_spawn(
        req, phase_scopes={"g3_test_gate": "implementation"}, path_config=cfg,
    ) == []


def test_module_contract_snapshot_matches_the_default_config_contract():
    """The historical module-level CONTRACT_TARGETS snapshot is exactly the full contract of
    the default config (fixed container targets + the config-derived repo-alias/.git + D-2
    auth set) — importers of the snapshot can never disagree with the runtime derivation."""
    assert contract_targets(_default_cfg()) == CONTRACT_TARGETS


# ── fb1_clone_mounted — the clone is the cell's world (the mount contract + its validation) ──


def _clone_phase_request(tmp_path, *, run_id="run-abc", verifier=False, scope="implementation"):
    """Build a clone-world request (agent or verifier) against a scratch config + clone path."""
    _repo, cfg = _make_config_repo(tmp_path)
    clone = cfg.runs_root / run_id / "repo"
    if verifier:
        req = build_verifier_request(
            {"name": "g3_test_gate", "kind": "test", "scope": scope,
             "tests": ["tests/test_spec_x.py"]},
            goal="g", workdir="/tmp/wt_x", model="deepseek/deepseek-v4-flash",
            spec_name="spec_x", path_config=cfg, run_clone=clone,
        )
        phase_name = "g3_test_gate"
    else:
        req = build_phase_request(
            {"name": "p1_slice1_base_supervisor", "scope": scope},
            goal="g", workdir="/tmp/wt", model="deepseek/deepseek-v4-pro",
            spec_name="spec_x", path_config=cfg, run_clone=clone,
        )
        phase_name = "p1_slice1_base_supervisor"
    return req, cfg, clone, phase_name


def test_clone_world_phase_request_sources_the_repo_from_the_run_clone(tmp_path):
    """(fb1 VERIFY a) a clone-world cell request's repo mount sources from the run clone — the
    mount source is runs_root/<run-id>/repo — and validates clean under the SAME config."""
    req, cfg, clone, phase_name = _clone_phase_request(tmp_path)
    assert req["run_clone"] == str(clone)
    repo_mounts = [m for m in req["mounts"] if m.get("target") == "/repo"]
    assert len(repo_mounts) == 1, f"expected exactly one /repo mount, got {req['mounts']}"
    repo_mount = repo_mounts[0]
    # the repo source is the run's clone: strictly under runs_root/<run-id>, never repo_root
    source = Path(repo_mount["source"]).resolve()
    assert source == clone.resolve()
    assert cfg.runs_root.resolve() in source.parents
    assert source.parent.name == "run-abc"
    # a commit-capable implementation cell mounts its clone rw (commits land in ITS clone)
    assert repo_mount["mode"] == "rw"
    assert validate_spawn(
        req, phase_scopes={phase_name: "implementation"}, path_config=cfg,
    ) == []


def test_clone_world_request_mounts_no_shared_worktree_or_shared_git(tmp_path):
    """(fb1 VERIFY b) a clone-world cell request mounts NEITHER the shared worktree NOR the
    shared .git — no /tmp namespace, no /repo/.git overlay, no D-16 host-path repo/.git alias,
    and no mount sources the shared worktrees_root or git_dir."""
    req, cfg, _clone, phase_name = _clone_phase_request(tmp_path)
    targets = {m.get("target"): m for m in req["mounts"]}
    sources = {str(m.get("source", "")) for m in req["mounts"]}

    # shared-worktree target (/tmp) and both shared-git spellings (/repo/.git overlay + the
    # host-path repo/.git aliases) are ABSENT
    assert "/tmp" not in targets
    assert "/repo/.git" not in targets
    assert str(cfg.repo_root) not in targets
    assert str(cfg.git_dir) not in targets
    # the shared sources never appear either
    assert str(cfg.worktrees_root) not in sources
    assert str(cfg.git_dir) not in sources
    assert str(cfg.repo_root) not in sources
    # the results/auth/state credential surface is still there (a clone cell is a real cell)
    assert "/app/experiments/results" in targets and targets["/app/experiments/results"]["mode"] == "rw"
    assert "/state" in targets and targets["/state"]["mode"] == "rw"
    assert validate_spawn(
        req, phase_scopes={phase_name: "implementation"}, path_config=cfg,
    ) == []


def test_clone_world_validation_refuses_a_request_that_would_mount_the_shared_git(tmp_path):
    """(fb1 VERIFY c) validation REFUSES a clone-world request that would mount the shared .git —
    by overlay target, by host-path .git alias target, and by a source inside the shared git dir."""
    req, cfg, _clone, phase_name = _clone_phase_request(tmp_path)
    base = dict(req)

    # (i) the shared /repo/.git overlay (a phase cell writing the SHARED git dir)
    tampered = {**base, "mounts": list(base["mounts"]) + [
        {"target": "/repo/.git", "source": str(cfg.git_dir), "mode": "rw"},
    ]}
    errors = validate_spawn(
        tampered, phase_scopes={phase_name: "implementation"}, path_config=cfg,
    )
    assert errors and any("step 3" in e and "shared" in e for e in errors), errors

    # (ii) the D-16 host-path .git alias (source + target = the shared git dir at its host path)
    tampered = {**base, "mounts": list(base["mounts"]) + [
        {"target": str(cfg.git_dir), "source": str(cfg.git_dir), "mode": "rw"},
    ]}
    errors = validate_spawn(
        tampered, phase_scopes={phase_name: "implementation"}, path_config=cfg,
    )
    assert errors and any("step 3" in e and "shared" in e for e in errors), errors

    # (iii) a source INSIDE the shared .git masked onto an otherwise-legal target
    tampered = {**base, "mounts": list(base["mounts"]) + [
        {"target": "/app/experiments/results", "source": str(cfg.git_dir / "objects"), "mode": "ro"},
    ]}
    errors = validate_spawn(
        tampered, phase_scopes={phase_name: "implementation"}, path_config=cfg,
    )
    assert errors and any("step 3" in e and "shared" in e for e in errors), errors

    # (iv) the whole shared worktree namespace mounted as /tmp is refused the same way
    tampered = {**base, "mounts": list(base["mounts"]) + [
        {"target": "/tmp", "source": str(cfg.worktrees_root), "mode": "rw"},
    ]}
    errors = validate_spawn(
        tampered, phase_scopes={phase_name: "implementation"}, path_config=cfg,
    )
    assert errors and any("step 3" in e and "shared" in e for e in errors), errors


def test_two_run_ids_produce_requests_with_distinct_clone_paths(tmp_path):
    """(fb1 VERIFY d) two run ids produce two cell requests referencing two DISTINCT clone
    paths — never the same runs_root/<run-id>/repo, so two concurrent cells never share git
    metadata through the request contract."""
    _repo, cfg = _make_config_repo(tmp_path)
    clone_a = cfg.runs_root / "run-aaa" / "repo"
    clone_b = cfg.runs_root / "run-bbb" / "repo"
    req_a = build_phase_request(
        {"name": "p1_slice1_base_supervisor", "scope": "implementation"},
        goal="g", workdir="/tmp/wt", model="deepseek/deepseek-v4-pro",
        spec_name="spec_x", path_config=cfg, run_clone=clone_a,
    )
    req_b = build_phase_request(
        {"name": "p1_slice1_base_supervisor", "scope": "implementation"},
        goal="g", workdir="/tmp/wt", model="deepseek/deepseek-v4-pro",
        spec_name="spec_x", path_config=cfg, run_clone=clone_b,
    )
    assert clone_a != clone_b
    assert req_a["run_clone"] != req_b["run_clone"]
    src_a = [m for m in req_a["mounts"] if m.get("target") == "/repo"][0]["source"]
    src_b = [m for m in req_b["mounts"] if m.get("target") == "/repo"][0]["source"]
    assert src_a == str(clone_a) and src_b == str(clone_b)
    assert src_a != src_b
    # each clone lives under its OWN run's root
    assert Path(src_a).parent == cfg.runs_root / "run-aaa"
    assert Path(src_b).parent == cfg.runs_root / "run-bbb"


def test_verifier_request_is_read_only_against_its_clone(tmp_path):
    """(fb1 VERIFY e) the verifier request is READ-ONLY against its clone — the candidate mount
    IS the run clone at /repo, every mount is ro, no shared surface, and it validates clean."""
    req, cfg, clone, phase_name = _clone_phase_request(tmp_path, verifier=True)
    assert req.get("verifier") is True
    assert req["run_clone"] == str(clone)
    assert all(m.get("mode") == "ro" for m in req["mounts"]), req["mounts"]
    repo_mounts = [m for m in req["mounts"] if m.get("target") == "/repo"]
    assert len(repo_mounts) == 1
    assert repo_mounts[0]["source"] == str(clone)
    assert cfg.runs_root.resolve() in Path(repo_mounts[0]["source"]).resolve().parents
    # the verifier carries no credential/state/results surface and no shared worktree/.git
    targets = {m.get("target") for m in req["mounts"]}
    assert not (targets & set(AUTH_DIRS))
    assert AUTH_CRED_FILE not in targets and STATE_TARGET not in targets
    assert "/tmp" not in targets and "/repo/.git" not in targets
    assert validate_spawn(
        req, phase_scopes={phase_name: "implementation"}, path_config=cfg,
    ) == []


def test_clone_world_readonly_scope_mounts_its_clone_read_only(tmp_path):
    """(fb1) a read-only-scope clone request (repo_readonly profile) mounts its clone ro — a
    research/adversarial cell reads the run clone, never writes it."""
    _repo, cfg = _make_config_repo(tmp_path)
    clone = cfg.runs_root / "run-ro" / "repo"
    req = build_phase_request(
        {"name": "p1_research_infra", "scope": "research_readonly"},
        goal="g", workdir="/tmp/wt", model="deepseek/deepseek-v4-pro",
        spec_name="spec_x", path_config=cfg, run_clone=clone,
    )
    assert req["mount_profile"] == "repo_readonly"
    repo_mounts = [m for m in req["mounts"] if m.get("target") == "/repo"]
    assert len(repo_mounts) == 1 and repo_mounts[0]["mode"] == "ro"
    assert repo_mounts[0]["source"] == str(clone)
    assert validate_spawn(
        req, phase_scopes={"p1_research_infra": "research_readonly"}, path_config=cfg,
    ) == []


def test_legacy_request_without_run_clone_keeps_the_shared_worktree_contract(tmp_path):
    """(fb1) the PRE-clone shared-worktree shape is unchanged — a request WITHOUT a run clone
    still mounts the shared worktree + shared .git overlays and validates under the legacy
    contract (backward-compatible callers that have not provisioned a clone are unaffected)."""
    _repo, cfg = _make_config_repo(tmp_path)
    req = build_phase_request(
        {"name": "p1_slice1_base_supervisor", "scope": "implementation"},
        goal="g", workdir="/tmp/wt", model="deepseek/deepseek-v4-pro",
        spec_name="spec_x", path_config=cfg,
    )
    assert "run_clone" not in req
    targets = {m.get("target"): m for m in req["mounts"]}
    assert "/tmp" in targets and targets["/tmp"]["mode"] == "rw"
    assert "/repo/.git" in targets and targets["/repo/.git"]["mode"] == "rw"
    assert targets["/repo"]["source"] == str(cfg.repo_root)
    assert validate_spawn(
        req, phase_scopes={"p1_slice1_base_supervisor": "implementation"}, path_config=cfg,
    ) == []


# ── build_verifier_request — the READ-ONLY-for-candidate contract (F1/g1_verifier_mount) ──


def _verifier_phase_def(**overrides) -> dict:
    phase = {
        "name": "g3_test_gate", "kind": "test", "scope": "implementation",
        "tests": ["tests/test_spec_x.py"],
    }
    phase.update(overrides)
    return phase


def _verifier_request(**overrides) -> dict:
    return build_verifier_request(
        _verifier_phase_def(),
        goal="g", workdir="/tmp/wt_x", model="deepseek/deepseek-v4-flash",
        spec_name="spec_x",
        command=["python3", "scripts/run_workflow.py", "--only-phase", "g3_test_gate",
                 "--no-commit"],
        **overrides,
    )


def test_verifier_request_mounts_the_candidate_read_only():
    """(a) a verifier request's worktree + .git mounts are READ-ONLY — the candidate the
    verifier runs its suite against is mounted ro (or absent), never rw: the worktree
    namespace, the repo, and both git dirs. Write protection is the mount contract, never a
    behavioral --no-commit."""
    cfg = _default_cfg()
    req = _verifier_request()
    by_target = {m.get("target"): m for m in req["mounts"]}

    # the candidate surface: worktree namespace (/tmp), repo (/repo), git dirs (/repo/.git +
    # the config's host-path repo alias + its .git) — all present, all ro.
    assert by_target["/tmp"]["mode"] == "ro"
    assert by_target["/repo"]["mode"] == "ro"
    assert by_target["/repo/.git"]["mode"] == "ro"
    assert by_target[str(cfg.repo_root)]["mode"] == "ro"
    assert by_target[str(cfg.git_dir)]["mode"] == "ro"
    # no remaining rw mount anywhere on the request
    assert all(m.get("mode") == "ro" for m in req["mounts"])

    # the verifier-forbidden surface is ABSENT (no credentials, no CLI state, no results)
    targets = {m.get("target") for m in req["mounts"]}
    assert not (targets & set(AUTH_DIRS))
    assert AUTH_CRED_FILE not in targets
    assert STATE_TARGET not in targets
    assert not any(t.startswith("/app/experiments/results") for t in targets)
    assert req.get("verifier") is True


def test_verifier_request_passes_validation():
    """A correctly-built verifier request (candidate ro, no forbidden surface) validates clean."""
    req = _verifier_request()
    assert validate_spawn(req, phase_scopes={"g3_test_gate": "implementation"}) == []


def test_verifier_request_that_would_mount_candidate_rw_fails_validation():
    """(b) a verifier request that would mount the candidate rw FAILS validation — before any
    spawn. Each writable candidate surface (worktree /tmp, git dirs) is refused."""
    cfg = _default_cfg()
    for tampered_target in ("/tmp", "/repo/.git", str(cfg.git_dir)):
        req = _verifier_request()
        for m in req["mounts"]:
            if m.get("target") == tampered_target:
                m["mode"] = "rw"
        errors = validate_spawn(req, phase_scopes={"g3_test_gate": "implementation"})
        assert errors, f"{tampered_target}: expected a validation refusal"
        assert any(
            "step 3" in e and "verifier" in e and "ro" in e and tampered_target in e
            for e in errors
        ), f"{tampered_target}: {errors}"


def test_verifier_request_rw_candidate_is_refused_before_any_spawn():
    """(b) the refusal is enforced at validation time — spawn_sibling never reaches the broker
    with a rw-candidate verifier request (the broker is never called)."""
    req = _verifier_request()
    for m in req["mounts"]:
        if m.get("target") == "/repo/.git":
            m["mode"] = "rw"
    with pytest.raises(SpawnValidationError) as exc:
        spawn_sibling(
            req,
            phase_scopes={"g3_test_gate": "implementation"},
        )
    assert any("step 3" in e and "verifier" in e for e in exc.value.errors)


def test_verifier_request_with_forbidden_surface_fails_validation():
    """A verifier request that carries a results/state/auth mount (a surface the builder never
    adds) is refused — read-only-for-candidate means ONLY the candidate surface, ro."""
    req = _verifier_request()
    req["mounts"].append({"target": "/app/experiments/results", "mode": "ro"})
    errors = validate_spawn(req, phase_scopes={"g3_test_gate": "implementation"})
    assert any("step 3" in e and "verifier" in e and "results" in e for e in errors)


def test_agent_phase_request_keeps_rw_candidate_mounts():
    """(c) the agent-phase executor's mounts are UNCHANGED — the implementation scope still
    gets rw worktree + rw git dirs (an agent phase COMMITS its work); the verifier is a
    DIFFERENT contract, and only the verifier request carries the marker."""
    cfg = _default_cfg()
    agent = build_phase_request(
        {"name": "p1_slice1_base_supervisor"},
        goal="g", workdir="/tmp/wt_x", model="deepseek/deepseek-v4-flash",
        spec_name="spec_x",
    )
    by_target = {m.get("target"): m for m in agent["mounts"]}
    assert by_target["/tmp"]["mode"] == "rw"
    assert by_target["/repo/.git"]["mode"] == "rw"
    assert by_target[str(cfg.git_dir)]["mode"] == "rw"
    assert agent.get("verifier") is None  # no marker: the agent contract, not the verifier's
    # the implementation request validates clean with its rw candidate (unchanged behavior)
    assert validate_spawn(agent) == []


def test_verifier_request_skips_the_d18_boot_probe_agent_does_not():
    """(ws4_smoke — THE SMOKE's wiring fix) a VERIFIER cell runs a SUITE and makes NO model
    call, so it mounts no CLI/auth dirs (the D-18 probe's whole premise) — its container boots
    with the entrypoint probe SKIPPED (FLEET_SKIP_PROBE=1, the same env the compose gives
    supervisor services that invoke no CLI). Before this fix a real verifier cell always died
    at boot: the probe found no opencode/claude (they are not mounted) and FAILED the container
    before the suite ever ran. An AGENT cell mounts the CLI dirs and must NOT skip the probe —
    it legitimately asserts the model CLIs resolve."""
    verifier = _verifier_request()
    assert verifier["env"].get("FLEET_SKIP_PROBE") == "1", (
        "a verifier cell (no credentials, no model CLI by construction) must skip the D-18 "
        "boot probe or it can never boot"
    )
    # ... while the agent (implementation) request does not carry the skip — its probe is real.
    agent = build_phase_request(
        {"name": "p1_slice1_base_supervisor", "scope": "implementation"},
        goal="g", workdir="/tmp/wt_x", model="deepseek/deepseek-v4-flash",
        spec_name="spec_x",
    )
    assert agent["env"].get("FLEET_SKIP_PROBE") in (None, "0")


def test_verifier_request_keeps_the_in_process_suite_target():
    """(d) the suite-target semantics are UNCHANGED — the verifier request runs the SAME
    target list the in-process LocalVerifier path would run (the phase's tests are carried on
    the phase def, never re-selected container-side)."""
    phase_def = _verifier_phase_def()
    req = build_verifier_request(
        phase_def,
        goal="g", workdir="/tmp/wt_x", model="deepseek/deepseek-v4-flash",
        spec_name="spec_x",
        command=["python3", "scripts/run_workflow.py", "--only-phase", "g3_test_gate",
                 "--no-commit"],
    )
    cmd = " ".join(str(c) for c in req.get("command", []))
    assert "--only-phase g3_test_gate" in cmd
    # the phase's own def — the source of the target list for the in-process run_suite — is
    # never rewritten or re-selected by the verifier request builder.
    assert phase_def["tests"] == ["tests/test_spec_x.py"]


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


def test_valid_submit_passes_validation():
    errors = validate_submit_request(_valid_submit_request())
    assert errors == []


def test_valid_submit_dispatch_builds_the_compose_run_argv(broker_seam):
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


def test_submit_model_outside_whitelist_fails():
    errors = validate_submit_request(_valid_submit_request(model="openai/gpt-6-hypothetical"))
    assert any("not in the model whitelist" in e for e in errors)


@pytest.mark.parametrize("model", sorted(MODEL_WHITELIST))
def test_every_whitelisted_model_passes_the_model_check(model):
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
    tmp_path, monkeypatch
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


def test_submit_mount_derivation_reuses_the_step_3_mount_contract_check():
    # Every phase in the real submit-verb spec is scope: implementation — its derived mounts
    # (build_phase_request) must land squarely inside CONTRACT_TARGETS, the same four-mount +
    # D-2 auth set every other spawn is checked against.
    errors = validate_submit_request(_valid_submit_request())
    assert not any("step 3" in e for e in errors)


# ── network = fleet-net (step 6) ────────────────────────────────────────────────


def test_submit_network_mismatch_fails():
    errors = validate_submit_request(_valid_submit_request(network="ai-infra"))
    assert any("!= fleet-net" in e for e in errors)


def test_submit_default_network_is_fleet_net():
    # fleet_manager submit never sets --network; the default must be the permitted value.
    errors = validate_submit_request(_valid_submit_request())
    assert not any("fleet-net" in e for e in errors)


# ── write flags declared (step 7) — "an undeclared write flag failing" (VERIFY) ─


def test_submit_actuation_armed_is_always_refused():
    request = _valid_submit_request(env={"FINOPS_ACTUATION_ARMED": "1"})
    errors = validate_submit_request(request)
    assert any("FINOPS_ACTUATION_ARMED is never set" in e for e in errors)

    with pytest.raises(SpawnValidationError) as exc:
        dispatch_submit(request, dry_run=False)
    assert any("FINOPS_ACTUATION_ARMED" in e for e in exc.value.errors)


def test_submit_kb_write_undeclared_without_an_implementation_phase_fails(tmp_path, monkeypatch):
    # A research_readonly-only spec never authorizes FINOPS_KB_WRITE — a request smuggling it
    # in must be refused, independent of the mount-contract checks (isolated via a scope that
    # doesn't touch the /repo-alias mount, so this doesn't need a configured repo root).
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


def test_submit_without_image_passes():
    # image is optional — absent entirely is the common case (fleet_manager submit without
    # --image), and must not fail step 8.
    errors = validate_submit_request(_valid_submit_request())
    assert not any("image" in e for e in errors)


def test_submit_with_a_valid_job_image_passes():
    errors = validate_submit_request(_valid_submit_request(image="fleet/job-example"))
    assert errors == []


@pytest.mark.parametrize(
    "image",
    [
        "fleet/base",           # the ladder's own cache root — never a job's to pick directly
        "fleet/orchestrator",   # the orchestrator's own image (socketless — the host broker holds the socket)
        "fleet/supervisor",
        "fleet/job-",           # no name after the prefix
        "fleet/job-Bad-Name",   # uppercase — outside JOB_IMAGE_PATTERN
        "evil/attacker-image",  # a third-party image entirely
        "fleet/job-x; rm -rf /",  # shell-metacharacter smuggling attempt
    ],
)
def test_submit_image_outside_the_job_namespace_fails(image):
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


def test_valid_submit_dispatch_with_image_reaches_the_compose_run_argv(broker_seam):
    result = dispatch_submit(_valid_submit_request(image="fleet/job-example"), dry_run=True)
    assert result["ok"] is True
    assert "--cell-image" in result["argv"]
    assert "fleet/job-example" in result["argv"]


# ── validate_fleet_command delegates "submit" whole (D-14 dispatch surface) ────


def test_validate_fleet_command_delegates_submit_to_validate_submit_request():
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
        self.eval_calls: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []

    def lpush(self, key: str, value: str) -> int:
        self._lists.setdefault(key, []).insert(0, value)
        return len(self._lists[key])

    def brpop(self, key: str, timeout: int | None = None):
        lst = self._lists.get(key)
        if not lst:
            return None
        return key, lst.pop()

    # Wave B2 claim lane: BLMOVE (claim), LREM (release), LRANGE (recovery scan).
    def blmove(self, first: str, second: str, timeout: int | None = None,
               src: str = "LEFT", dest: str = "RIGHT"):
        lst = self._lists.get(first)
        if not lst:
            return None
        value = lst.pop(0) if src == "LEFT" else lst.pop()
        dst = self._lists.setdefault(second, [])
        if dest == "LEFT":
            dst.insert(0, value)
        else:
            dst.append(value)
        return value

    def lrem(self, key: str, count: int, value: str) -> int:
        lst = self._lists.get(key, [])
        removed = 0
        while value in lst and (count == 0 or removed < count):
            lst.remove(value)
            removed += 1
        return removed

    def eval(self, script: str, numkeys: int, *args):
        """The one server-side script the wrapper uses: `_requeue_claimed`'s atomic move."""
        self.eval_calls.append((script, tuple(args[:numkeys]), tuple(args[numkeys:])))
        if "LREM" in script and "LPUSH" in script:
            self.lrem(args[0], 1, args[2])
            self.lpush(args[1], args[2])
            return 1
        raise NotImplementedError(script)

    def lrange(self, key: str, start: int, end: int) -> list[str]:
        lst = self._lists.get(key, [])
        if end == -1:
            return list(lst[start:])
        return list(lst[start : end + 1])

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
def _noop_spec():
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
    _noop_spec, monkeypatch, broker_seam,
):
    fleet_manager = _fleet_manager_module()
    spec_path, ledger_dir = _noop_spec
    ledger_dir.mkdir(parents=True, exist_ok=True)
    # ANOTHER run's pre-existing ledger: the job must never be pointed at it (Wave B1 —
    # the association is by difference, not by "newest file in the directory").
    other_run = ledger_dir / "20260901T000000Z.json"
    other_run.write_text("{}")

    r = _FakeCommandsRedis()
    cmd = fleet_manager._send_submit_command(
        r, spec=_NOOP_SPEC_REL, goal="run the no-op phase",
        model="anthropic/claude-sonnet-5", workdir="/tmp/wt_launch_handler_test",
    )
    assert fleet_manager.build_board(r)["jobs"][0]["status"] == "launching"

    calls = []
    this_run = ledger_dir / "20260912T164142123456Z_run-new.json"

    def fake_run(argv, check=False, **_kwargs):
        calls.append(argv)
        # The dispatched run writes ITS OWN ledger and NAMES it on stderr — the identity the
        # wrapper selects by (Wave F7).
        this_run.write_text(json.dumps({"run_id": "run-new", "phases": []}))
        return subprocess.CompletedProcess(
            argv, returncode=0, stdout="{}", stderr=f"ledger: {this_run}\n",
        )

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
    assert job["ledger"] == str(this_run)  # ITS ledger — never the pre-existing other run's
    assert job["run_id"] == "run-new"      # ... and the run's OWN identity rides the record
    import hashlib

    assert job["ledger_sha256"] == hashlib.sha256(this_run.read_bytes()).hexdigest()


def test_consume_fleet_commands_nonzero_exit_marks_failed_and_files_the_dlq(
    _noop_spec, monkeypatch, broker_seam,
):
    fleet_manager = _fleet_manager_module()
    r = _FakeCommandsRedis()
    cmd = fleet_manager._send_submit_command(
        r, spec=_NOOP_SPEC_REL, goal="run the no-op phase",
        model="deepseek/deepseek-v4-pro", workdir="/tmp/wt_launch_handler_test",
    )

    monkeypatch.setattr(
        subprocess, "run",
        lambda argv, check=False, **kwargs: subprocess.CompletedProcess(
            argv, returncode=1, stdout="", stderr="",
        ),
    )

    consume_fleet_commands(client=r, once=True)

    job = fleet_manager.build_board(r)["jobs"][0]
    assert job["job_id"] == cmd["job_id"]
    assert job["status"] == "failed"
    assert job["returncode"] == 1
    # A failed run that named no ledger gets an honest null — never a directory-diff guess.
    assert job["ledger"] is None

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


def test_consume_fleet_commands_dry_run_never_calls_subprocess(_noop_spec, monkeypatch,
                                                               broker_seam):
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


# ── Wave F7: a job's ledger association is the run's OWN identity ───────────


def test_run_identity_reads_the_runs_own_ledger_line(tmp_path):
    """The run names its ledger on stderr; the board record carries the exact path, the
    ledger's own run_id, and the sha256 over its bytes — identity, not a diff."""
    import hashlib

    from scripts.fleet import spawn_wrapper as sw

    ledger_dir = tmp_path / "experiments" / "results" / "workflows" / "demo"
    ledger_dir.mkdir(parents=True)
    ledger = ledger_dir / "20260912T164142123456Z_run-new.json"
    ledger.write_text(json.dumps({"run_id": "run-new", "phases": []}))

    identity = sw._run_identity("demo", {
        "returncode": 0,
        "stdout": '{"run_id": "run-new"}',
        "stderr": f"some warning\nledger: {ledger}\n",
    })
    assert identity["ledger"] == str(ledger)
    assert identity["run_id"] == "run-new"
    assert identity["ledger_sha256"] == hashlib.sha256(ledger.read_bytes()).hexdigest()


def test_run_identity_is_empty_when_the_output_names_no_ledger(tmp_path):
    """A new ledger file appearing in the spec dir is NOT an association: without the run's
    own ``ledger:`` line the identity is honestly empty — never diff/recency selection."""
    from scripts.fleet import spawn_wrapper as sw

    ledger_dir = tmp_path / "experiments" / "results" / "workflows" / "demo"
    ledger_dir.mkdir(parents=True)
    (ledger_dir / "20260912T164142123456Z_run-someone-else.json").write_text("{}")

    identity = sw._run_identity("demo", {
        "returncode": 0, "stdout": "{}", "stderr": "no ledger line here",
    })
    assert identity == {"ledger": "", "run_id": "", "ledger_sha256": ""}


def test_run_identity_rejects_a_ledger_outside_the_specs_directory(tmp_path):
    """The named path must be THIS spec's ledger: an unrelated (or forged) path printed by
    a confused run cannot become this job's result association."""
    from scripts.fleet import spawn_wrapper as sw

    other_dir = tmp_path / "experiments" / "results" / "workflows" / "other_spec"
    other_dir.mkdir(parents=True)
    foreign = other_dir / "20260912T164142123456Z_run-x.json"
    foreign.write_text(json.dumps({"run_id": "run-x"}))

    identity = sw._run_identity("demo", {"stderr": f"ledger: {foreign}\n"})
    assert identity["ledger"] == ""


def test_two_concurrent_same_spec_dispatches_keep_distinct_result_associations(
    _noop_spec, monkeypatch, broker_seam,
):
    """The identity-recovery contract, pinned against true concurrency.

    Both dispatches take their (now removed) directory snapshots BEFORE either run writes,
    then each run writes its own ledger and names it; the old whole-directory diff resolved
    BOTH jobs to the lexicographically last new file. With identity selection each board
    record keeps its OWN run's ledger, run_id, and digest.
    """
    import hashlib
    import threading

    fleet_manager = _fleet_manager_module()
    _spec_path, ledger_dir = _noop_spec
    ledger_dir.mkdir(parents=True, exist_ok=True)

    # Two submits of the SAME spec, queued in the claim lane.
    r = _FakeCommandsRedis()
    _push_submit(r, job_id="job-noop-1", nonce="one")
    _push_submit(r, job_id="job-noop-2", nonce="two")

    # Both fake runs meet at the barrier BEFORE writing anything, so both ledgers exist
    # before either dispatch resolves — the exact window the diff-based selection failed in.
    barrier = threading.Barrier(2)

    def fake_run(argv, check=False, **_kwargs):
        barrier.wait(timeout=10)
        cell_env = next(arg for arg in argv if arg.startswith("FINOPS_CELL_ID="))
        job_id = cell_env.split("=", 1)[1]
        ledger = ledger_dir / f"20260912T164142123456Z_{job_id}.json"
        ledger.write_text(json.dumps({"run_id": f"run-{job_id}", "phases": []}))
        return subprocess.CompletedProcess(
            argv, returncode=0, stdout="{}", stderr=f"ledger: {ledger}\n",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    # ``once`` processes exactly ONE command; a bounded batch claims and dispatches both.
    consume_fleet_commands(client=r, max_commands=2)

    by_id = {job["job_id"]: job for job in fleet_manager.build_board(r)["jobs"]}
    first, second = by_id["job-noop-1"], by_id["job-noop-2"]
    assert first["ledger"].endswith("_job-noop-1.json")
    assert second["ledger"].endswith("_job-noop-2.json")
    assert first["run_id"] == "run-job-noop-1"
    assert second["run_id"] == "run-job-noop-2"
    assert first["ledger_sha256"] == hashlib.sha256(
        (ledger_dir / "20260912T164142123456Z_job-noop-1.json").read_bytes()
    ).hexdigest()
    assert first["ledger_sha256"] != second["ledger_sha256"]


# ── Wave F7: restart recovery moves commands atomically ─────────────────────


def test_recovery_requeues_a_control_action_in_one_atomic_move():
    """The requeue is ONE server-side script (LREM+LPUSH) — never a client-side pair whose
    interruption between LREM and LPUSH would leave the command in neither lane."""
    from scripts.fleet import spawn_wrapper as sw

    r = _FakeCommandsRedis()
    raw = json.dumps({"action": "scale", "service": "workflow-runner", "count": 2,
                      "ts": 0.0, "nonce": "n"})
    r.lpush(sw.PROCESSING_KEY, raw)

    tally = sw._recover_processing(r, _fleet_manager_module(), _fake_dlq())

    assert tally["requeued"] == 1
    assert r._lists.get(sw.COMMANDS_KEY) == [raw]
    assert r._lists.get(sw.PROCESSING_KEY, []) == []
    assert len(r.eval_calls) == 1  # the move was one atomic EVAL, not LREM-then-LPUSH


def test_recovery_interrupted_before_the_move_loses_nothing():
    """If the atomic move cannot run (Redis dropped), the claim stays in PROCESSING — a
    later recovery pass moves it. The command is never absent from both lanes."""
    from scripts.fleet import spawn_wrapper as sw

    raw = json.dumps({"action": "drain", "service": "workflow-runner",
                      "ts": 0.0, "nonce": "n"})

    class _DownMidMove(_FakeCommandsRedis):
        def eval(self, script, numkeys, *args):
            raise ConnectionError("redis dropped before the script ran")

    down = _DownMidMove()
    down.lpush(sw.PROCESSING_KEY, raw)

    with pytest.raises(ConnectionError):
        sw._recover_processing(down, _fleet_manager_module(), _fake_dlq())
    # Nothing was moved and nothing was lost: the claim is still recoverable.
    assert down._lists.get(sw.PROCESSING_KEY) == [raw]
    assert down._lists.get(sw.COMMANDS_KEY, []) == []

    recovered = _FakeCommandsRedis()
    recovered.lpush(sw.PROCESSING_KEY, raw)
    tally = sw._recover_processing(recovered, _fleet_manager_module(), _fake_dlq())
    assert tally["requeued"] == 1
    assert recovered._lists.get(sw.COMMANDS_KEY) == [raw]


def _fake_dlq():
    class _DLQ:
        def record_dead(self, client, queue, command, reason):
            return None

    return _DLQ()


# ── wave C follow-up: the spec-resolution refusal names its root ─────────────


def test_resolve_spec_path_names_the_root(tmp_path):
    """A missing spec names the ROOT it was resolved under (the container's /repo mount is
    often not the tree the operator edited — the bare refusal cost two deploy cycles)."""
    from scripts.fleet import spawn_wrapper as sw

    path, errors = sw._resolve_spec_path("workflows/repository/nope.yaml", tmp_path)
    assert path is None and len(errors) == 1
    assert "does not resolve to a file under" in errors[0]
    assert str(tmp_path) in errors[0]


# ── the armed verifier lease exemption (admission-armed gap, decision 39be8e563d7c) ──


def test_armed_verifier_spawn_needs_no_lease_block(tmp_path, monkeypatch):
    """The verifier is a read-only pytest cell that spends no model dollars and deliberately
    stamps no lease block; the armed gate exempts VERIFIER-marked requests. The carve-out is
    structural — step 3 locks a marked request's mounts to verifier_readonly with no network,
    so an agent cell cannot ride the marker past the gate."""
    from scripts.fleet import spawn_wrapper as sw

    _repo, cfg = _make_config_repo(tmp_path)
    req = build_verifier_request(
        {"name": "g3_test_gate", "kind": "test", "scope": "implementation",
         "tests": ["tests/test_spec_x.py"]},
        goal="g", workdir="/tmp/wt_x", model="deepseek/deepseek-v4-flash",
        spec_name="spec_x", path_config=cfg,
    )
    assert "verifier" in req  # the marker is the exemption's key, not the absence of fields
    monkeypatch.setattr(sw, "admission_required", lambda: True)
    errors = validate_spawn(
        req, phase_scopes={"g3_test_gate": "implementation"}, path_config=cfg,
    )
    assert errors == []


def test_armed_verifier_with_a_partial_lease_block_still_refuses(tmp_path, monkeypatch):
    """A verifier that LOOKS budgeted and is not is the same hazard as any cell — the
    exemption only covers a wholly absent block."""
    from scripts.fleet import spawn_wrapper as sw

    _repo, cfg = _make_config_repo(tmp_path)
    req = build_verifier_request(
        {"name": "g3_test_gate", "kind": "test", "scope": "implementation",
         "tests": ["tests/test_spec_x.py"]},
        goal="g", workdir="/tmp/wt_x", model="deepseek/deepseek-v4-flash",
        spec_name="spec_x", path_config=cfg,
    )
    req["reserved_cost_usd"] = 0.6
    monkeypatch.setattr(sw, "admission_required", lambda: True)
    errors = validate_spawn(
        req, phase_scopes={"g3_test_gate": "implementation"}, path_config=cfg,
    )
    assert any("partial lease block" in e for e in errors)


def test_armed_non_verifier_spawn_still_requires_the_lease_block(tmp_path, monkeypatch):
    """The carve-out never widens: an ordinary (agent-shaped) spawn without a lease block
    still refuses at step 6 when the gate is armed."""
    from scripts.fleet import spawn_wrapper as sw

    _repo, cfg = _make_config_repo(tmp_path)
    req = build_phase_request(
        {"name": "p1_slice1_base_supervisor", "scope": "implementation"},
        goal="g", workdir="/tmp/wt_x", model="deepseek/deepseek-v4-flash",
        spec_name="spec_x", image="fleet/base", path_config=cfg,
    )
    monkeypatch.setattr(sw, "admission_required", lambda: True)
    errors = validate_spawn(
        req, phase_scopes={"p1_slice1_base_supervisor": "implementation"}, path_config=cfg,
    )
    assert any("lease block missing" in e for e in errors)


def test_submit_extended_fields_are_type_validated():
    """Step 10: the identity fields that must survive every hop are type-checked here — a
    malformed digest/continuation/admission refuses with the rest of the submit."""
    base = _valid_submit_request()

    bad_digest = dict(base, spec_sha256="not-hex")
    assert any("spec_sha256 must be a 64-character hex" in e
               for e in validate_submit_request(bad_digest))

    bad_resume = dict(base, resume="yes")
    assert any("resume must be a boolean" in e
               for e in validate_submit_request(bad_resume))

    orphan_parent = dict(base, parent_run_id="run-1")
    assert any("resume must be true" in e
               for e in validate_submit_request(orphan_parent))

    bad_admission = dict(base, admission={"required": "yes"})
    assert any("admission.required must be a boolean" in e
               for e in validate_submit_request(bad_admission))

    bad_budget = dict(base, admission={"required": True, "campaign_budget_usd": -1})
    assert any("campaign_budget_usd" in e
               for e in validate_submit_request(bad_budget))

    good = dict(base, spec_sha256="a" * 64, resume=True, parent_run_id="run-1",
                admission={"required": True, "campaign_budget_usd": 20.0})
    assert validate_submit_request(good) == []


def test_submit_execution_settings_are_type_validated():
    """Step 11: an accepted-but-malformed execution setting refuses — a typo can never
    silently become the orchestrator default (Astra finding)."""
    base = _valid_submit_request()
    bad_backend = dict(base, execution={"backend": "gemini"})
    assert any("execution.backend" in e for e in validate_submit_request(bad_backend))
    bad_effort = dict(base, execution={"thinking_effort": "  "})
    assert any("execution.thinking_effort" in e for e in validate_submit_request(bad_effort))
    bad_budget = dict(base, execution={"thinking_budget_tokens": -1})
    assert any("execution.thinking_budget_tokens" in e for e in validate_submit_request(bad_budget))
    bad_nocommit = dict(base, execution={"no_commit": "yes"})
    assert any("execution.no_commit" in e for e in validate_submit_request(bad_nocommit))
    good = dict(base, execution={
        "backend": "opencode", "thinking_effort": "high",
        "thinking_budget_tokens": 12000, "output_token_limit": 64000,
        "timeout_seconds": 2400, "no_commit": False,
    })
    assert validate_submit_request(good) == []


def test_submit_admission_reserve_and_cap_are_type_validated():
    """A malformed reserve/cap refuses with the rest of the submit; a positive reserve passes."""
    base = _valid_submit_request()
    bad_reserve = dict(base, admission={"required": True, "reserve_usd": 0})
    assert any("reserve_usd must be a positive number" in e
               for e in validate_submit_request(bad_reserve))
    bad_cap = dict(base, admission={"required": True, "hard_cap_usd": -1})
    assert any("hard_cap_usd must be a non-negative number" in e
               for e in validate_submit_request(bad_cap))
    good = dict(base, admission={"required": True, "reserve_usd": 0.6, "hard_cap_usd": 1.0})
    assert validate_submit_request(good) == []


# ── The AIO binding gate (Unit D) ─────────────────────────────────────────────
#
# A submit carrying an ``aio`` block declares the AIO actor: the wrapper (and, independently,
# the broker) resolves the binding from the durable store BY IDENTITY — the request's own
# claims are never proof — and the AIO session's measured budget must allow new consequential
# work. A submit with no ``aio`` block keeps its existing contract.


def _aio_request(*, aio: dict) -> dict:
    """A manager-shaped AIO submit: actor + block together (the consistent declaration)."""
    return _valid_submit_request(actor="aio", aio=aio)


def _aio_block(**overrides) -> dict:
    block = {
        "native_session_id": "ses_aio",
        "agent": "aio-control",
        "binding_id": "",
        "task_revision": 1,
    }
    block.update(overrides)
    return block


def _bound_store(store, *, project: str = "") -> str:
    """A tmp binding store with ONE real binding; returns its AUTHORIZATION identity.

    The exec gate checks the binding's authorization identity (round-9): stable across
    routine progress recording, advanced only by task-definition changes.
    """
    from agentic_dynamics.knowledge import session_ingestion as si

    si.init_binding_store(store)
    result = si.write_binding(
        {
            "native_session_id": "ses_aio",
            "resolved_agent": "aio-control",
            "task_identity": "unit-d",
            "original_request": "enforce the binding at the exec boundary",
            "project": project,
        },
        artifact_dir=store,
        publish=False,
    )
    assert result.status == si.BINDING_STATUS_CREATED
    binding = si.read_binding("ses_aio", artifact_dir=store).binding or {}
    return si.binding_authorization_id(binding)


@pytest.fixture
def aio_env(tmp_path, monkeypatch):
    """Point the gate at a tmp store; stub the budget measurement to OK unless overridden."""
    from scripts.fleet import spawn_wrapper as sw

    monkeypatch.setenv("FINOPS_KB_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setattr(
        sw, "_aio_budget_verdict",
        lambda session_id: {
            "verdict": "OK", "reason": "", "backend_available": True, "measured": True,
        },
    )
    return tmp_path


def test_a_bound_aio_submit_passes_the_binding_gate(aio_env):
    binding_id = _bound_store(aio_env)
    errors = validate_submit_request(
        _aio_request(aio=_aio_block(binding_id=binding_id))
    )
    assert errors == []


def test_an_aio_submit_without_a_store_is_refused(tmp_path, monkeypatch):
    from scripts.fleet import spawn_wrapper as sw

    monkeypatch.setenv("FINOPS_KB_ARTIFACT_DIR", str(tmp_path / "absent"))
    monkeypatch.setattr(
        sw, "_aio_budget_verdict",
        lambda session_id: {
            "verdict": "OK", "reason": "", "backend_available": True, "measured": True,
        },
    )
    errors = validate_submit_request(_aio_request(aio=_aio_block(binding_id="0" * 64)))
    assert any("binding store is unavailable" in e for e in errors)


def test_an_aio_submit_without_a_binding_is_refused(aio_env):
    errors = validate_submit_request(_aio_request(aio=_aio_block(binding_id="0" * 64)))
    assert any("no durable AIO binding" in e for e in errors)


def test_a_foreign_binding_id_is_refused(aio_env):
    _bound_store(aio_env)
    errors = validate_submit_request(_aio_request(aio=_aio_block(binding_id="f" * 64)))
    assert any("does not match the binding's authorization identity" in e for e in errors)


def test_a_mismatched_agent_is_refused(aio_env):
    binding_id = _bound_store(aio_env)
    errors = validate_submit_request(
        _aio_request(aio=_aio_block(binding_id=binding_id, agent="build"))
    )
    assert any("resolved agent" in e for e in errors)


def test_a_stale_task_revision_is_refused_and_the_current_one_passes(aio_env):
    """A GENUINE task change advances the authorization epoch: commands minted against the
    old definition are refused; the current authorization passes."""
    from agentic_dynamics.knowledge import session_ingestion as si

    _bound_store(aio_env)
    updated = si.update_binding_context(
        "ses_aio", context={"work_unit": "v2"}, expected_version=1,
        artifact_dir=aio_env, publish=False,
    )
    binding = updated.binding or {}
    auth_id = si.binding_authorization_id(binding)
    assert si.binding_authorization_version(binding) == 2
    stale = validate_submit_request(
        _aio_request(aio=_aio_block(binding_id=auth_id, task_revision=1))
    )
    assert any("stale task revision" in e for e in stale)
    current = validate_submit_request(
        _aio_request(aio=_aio_block(binding_id=auth_id, task_revision=2))
    )
    assert current == []


def test_progress_recording_does_not_advance_the_authorization(aio_env):
    """Round-9: routine progress (next_action) preserves the authorization — a command
    minted before the recording still passes AFTER it (the coupling defect's unit form)."""
    from agentic_dynamics.knowledge import session_ingestion as si

    auth_id = _bound_store(aio_env)
    updated = si.update_binding_context(
        "ses_aio", context={"next_action": "observe job X"}, expected_version=1,
        artifact_dir=aio_env, publish=False,
    )
    binding = updated.binding or {}
    assert si.binding_authorization_id(binding) == auth_id  # stable
    assert si.binding_authorization_version(binding) == 1  # epoch unchanged
    assert int(binding.get("context_version") or 0) == 2  # the progress counter advanced
    errors = validate_submit_request(
        _aio_request(aio=_aio_block(binding_id=auth_id, task_revision=1))
    )
    assert errors == []


def test_capacity_verdicts_are_advisory_at_the_gate(aio_env, monkeypatch):
    """The 2026-09-16 policy: conversation capacity is ADVISORY to workflow admission.
    Every verdict — including COMPACT (native boundary), CLOSE (hard limit), and UNJUDGED
    (no measurement) — leaves a valid bound submission untouched; the report is measured
    separately (``aio_capacity_report``) and never enters the refusal list."""
    from scripts.fleet import spawn_wrapper as sw

    binding_id = _bound_store(aio_env)
    for verdict in ("OK", "WARN", "COMPACT", "CLOSE", "UNJUDGED"):
        monkeypatch.setattr(
            sw, "_aio_budget_verdict",
            lambda session_id, v=verdict: {
                "verdict": v, "reason": "measured reason",
                "backend_available": True, "measured": True,
            },
        )
        errors = validate_submit_request(
            _aio_request(aio=_aio_block(binding_id=binding_id))
        )
        assert errors == [], f"{verdict} must not block: {errors}"
        assert sw.aio_capacity_report("ses_aio") == {
            "verdict": verdict,
            "reason": "measured reason",
            "backend_available": True,
            "measured": True,
            "advisory": True,
        }, verdict


def test_the_capacity_report_reports_unmeasurable_honestly(aio_env, monkeypatch):
    """An unmeasurable reading is reported — with its reason — as an unavailable advisory:
    never a refusal, never silently upgraded to OK, and never a claimed measurement."""
    from scripts.fleet import spawn_wrapper as sw

    monkeypatch.setattr(
        sw, "_aio_budget_verdict",
        lambda session_id: {
            "verdict": "UNJUDGED", "reason": "db unavailable",
            "backend_available": False, "measured": False,
        },
    )
    assert sw.aio_capacity_report("ses_aio") == {
        "verdict": "UNJUDGED",
        "reason": "db unavailable",
        "backend_available": False,
        "measured": False,
        "advisory": True,
    }


def test_a_corrupt_db_reports_backend_reachable_and_not_measured(tmp_path, monkeypatch):
    """The reviewer's reproduction (2026-09-16): a reachable-but-unreadable database must
    never read as ``measured`` — the two availability facts are told apart."""
    from scripts.fleet import spawn_wrapper as sw

    _capacity_env(tmp_path, monkeypatch)
    db = tmp_path / "corrupt.db"
    db.write_bytes(b"this is not a sqlite database" * 100)
    monkeypatch.setenv("FINOPS_OPENCODE_DB", str(db))
    report = sw._aio_budget_verdict("ses_aio")
    assert report["verdict"] == "UNJUDGED"
    assert report["backend_available"] is True and report["measured"] is False
    assert "not a database" in report["reason"]
    full = sw.aio_capacity_report("ses_aio")
    assert full["advisory"] is True and full["measured"] is False


def test_the_budget_verdict_is_measured_from_the_explicit_session(tmp_path, monkeypatch):
    """The gate measures the binding's OWN session; an unknown session is UNJUDGED."""
    import json as _json
    import sqlite3

    from scripts.fleet import spawn_wrapper as sw

    _capacity_env(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE session (id TEXT, time_updated INTEGER, model TEXT, version TEXT, directory TEXT)"
    )
    con.execute("CREATE TABLE message (session_id TEXT, time_created INTEGER, data TEXT)")
    con.execute(
        "INSERT INTO session VALUES ('ses_aio', 200, ?, '1.18.15', '/nonexistent/project')",
        (_json.dumps({"providerID": "deepseek", "id": "deepseek-v4-flash"}),),
    )
    con.execute(
        "INSERT INTO message VALUES ('ses_aio', 1, ?)",
        (_json.dumps({"role": "assistant", "tokens": {"total": 20, "input": 10}}),),
    )
    con.commit()
    con.close()
    monkeypatch.setenv("FINOPS_OPENCODE_DB", str(db))
    report = sw._aio_budget_verdict("ses_aio")
    assert report["verdict"] == "OK" and report["reason"] == ""
    assert report["backend_available"] is True and report["measured"] is True
    report = sw._aio_budget_verdict("ses_unknown")
    assert report["verdict"] == "UNJUDGED" and "does not exist" in report["reason"]
    # The backend WAS reachable; the identity is what failed — neither flag claims a reading.
    assert report["backend_available"] is True and report["measured"] is False


def test_a_malformed_aio_block_is_refused():
    errors = validate_submit_request(_valid_submit_request(actor="aio", aio={}))
    assert any("native_session_id is required" in e for e in errors)
    assert any("aio.agent is required" in e for e in errors)
    assert any("binding_id is required" in e for e in errors)
    assert any("task_revision must be a positive integer" in e for e in errors)


def test_a_non_aio_submit_needs_no_binding_and_keeps_its_contract(tmp_path, monkeypatch):
    """Valid non-AIO automation (workers, campaign scripts) never impersonates the AIO — and
    a missing binding store does not touch it."""
    monkeypatch.setenv("FINOPS_KB_ARTIFACT_DIR", str(tmp_path / "absent"))
    assert validate_submit_request(_valid_submit_request()) == []


# ── The budget at the Docker boundary (reviewer repair, 2026-09-15) ───────────
#
# The containerized orchestrator has no host session database mounted: a gate that cannot
# measure must DEFER to the host gate (which owns the canonical DB), never fabricate
# UNJUDGED and block a valid job. The host gate (the broker) measures strictly.


_CAPACITY_CATALOG = {
    "deepseek": {
        "models": {"deepseek-v4-flash": {"limit": {"context": 1_000_000, "output": 384_000}}}
    }
}


def _capacity_env(tmp_path, monkeypatch) -> None:
    """Hermetic capacity resolution: a tmp catalog + tmp config roots (no host config)."""
    import json as _json

    cache = tmp_path / "models.json"
    cache.write_text(_json.dumps(_CAPACITY_CATALOG), encoding="utf-8")
    monkeypatch.setenv("FINOPS_OPENCODE_MODELS_CACHE", str(cache))
    # Deterministic limits: the fixture catalog, never the host runtime CLI.
    monkeypatch.setenv("FINOPS_SESSION_CAPACITY_SOURCE", "catalog")
    (tmp_path / "config-home").mkdir(exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config-home"))


def _canonical_session_db(path, *, sid: str = "ses_aio", turns: int = 1, context: int = 10,
                          pending_only: bool = False, model: str = "deepseek-v4-flash") -> None:
    """A real opencode-shaped session db (production schema + the ACTIVE model), not a mock."""
    import json as _json
    import sqlite3

    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE session (id TEXT, time_updated INTEGER, model TEXT, version TEXT, directory TEXT)"
    )
    con.execute("CREATE TABLE message (session_id TEXT, time_created INTEGER, data TEXT)")
    con.execute(
        "INSERT INTO session VALUES (?, 200, ?, '1.18.15', ?)",
        (sid, _json.dumps({"providerID": "deepseek", "id": model}), "/nonexistent/project"),
    )
    if pending_only:
        con.execute(
            "INSERT INTO message VALUES (?, 1, ?)",
            (sid, _json.dumps({"role": "assistant", "tokens": {"total": 0, "input": 0, "output": 0}})),
        )
    else:
        for i in range(turns - 1):
            con.execute(
                "INSERT INTO message VALUES (?, ?, ?)",
                (sid, i, _json.dumps({"role": "assistant", "tokens": {"total": 10, "input": 10}})),
            )
        con.execute(
            "INSERT INTO message VALUES (?, ?, ?)",
            (sid, turns, _json.dumps(
                {"role": "assistant", "tokens": {"total": context, "input": context}}
            )),
        )
    con.commit()
    con.close()


def _valid_bound_request(tmp_path, monkeypatch, *, db_name: str | None, **store_kwargs) -> tuple[dict, str]:
    from agentic_dynamics.knowledge import session_ingestion as si

    store = tmp_path / "kb"
    si.init_binding_store(store)
    binding_id = _bound_store(store, **store_kwargs)
    monkeypatch.setenv("FINOPS_KB_ARTIFACT_DIR", str(store))
    if db_name is not None:
        _canonical_session_db(tmp_path / db_name)
        monkeypatch.setenv("FINOPS_OPENCODE_DB", str(tmp_path / db_name))
    return _aio_request(aio=_aio_block(binding_id=binding_id)), binding_id


def test_a_gate_without_the_session_db_never_refuses_a_valid_binding(tmp_path, monkeypatch):
    """THE Docker-shape proof: the containerized wrapper has no host DB — a valid binding
    passes, and the capacity reading is reported as an unavailable ADVISORY with a reason
    (2026-09-16 policy: never converted into a refusal)."""
    from scripts.fleet import spawn_wrapper as sw

    request, _ = _valid_bound_request(tmp_path, monkeypatch, db_name=None)
    monkeypatch.setenv("FINOPS_OPENCODE_DB", str(tmp_path / "absent.db"))
    assert validate_submit_request(request) == []
    report = sw.aio_capacity_report("ses_aio")
    assert report["verdict"] == "UNJUDGED" and report["measured"] is False
    assert report["backend_available"] is False
    assert "not found" in report["reason"]


def test_the_capacity_reading_never_becomes_an_authorization_failure(tmp_path, monkeypatch):
    """The 2026-09-16 separation, end to end: an unmeasurable capacity reading refuses
    NOTHING, while the binding refusals are untouched (the retired strict gate's regression
    pair — the missing measurement is not a missing authorization)."""
    request, _ = _valid_bound_request(tmp_path, monkeypatch, db_name=None)
    monkeypatch.setenv("FINOPS_OPENCODE_DB", str(tmp_path / "absent.db"))
    assert validate_submit_request(request) == []
    broken = {**request, "aio": {**_aio_block(binding_id="f" * 64)}}
    errors = validate_submit_request(broken)
    assert any("does not match the binding's authorization identity" in e for e in errors)


def test_validate_submit_cli_reports_capacity_as_advisory(tmp_path, monkeypatch, capsys):
    """The CLI surface: ``validate-submit`` emits a structured ``aio_capacity`` ADVISORY
    block — present, honest about being unmeasured, and never part of ``errors``."""
    import io
    import json as _json

    from scripts.fleet import spawn_wrapper as sw

    request, _ = _valid_bound_request(tmp_path, monkeypatch, db_name=None)
    monkeypatch.setenv("FINOPS_OPENCODE_DB", str(tmp_path / "absent.db"))
    monkeypatch.setattr("sys.stdin", io.StringIO(_json.dumps(request)))
    rc = sw.main(["validate-submit"])
    payload = _json.loads(capsys.readouterr().out.strip())
    assert rc == 0 and payload["ok"] is True and payload["errors"] == []
    assert payload["aio_capacity"]["advisory"] is True
    assert payload["aio_capacity"]["verdict"] == "UNJUDGED"
    assert payload["aio_capacity"]["measured"] is False


def test_the_budget_is_measured_for_real_and_never_blocks(tmp_path, monkeypatch):
    """No verdict mocking: a real opencode-shaped DB drives the ADVISORY report, and the
    gate itself never refuses on capacity — at any reading (2026-09-16 policy)."""
    from scripts.fleet import spawn_wrapper as sw

    _capacity_env(tmp_path, monkeypatch)
    request, _ = _valid_bound_request(tmp_path, monkeypatch, db_name="ok.db")
    assert validate_submit_request(request) == []
    assert sw.aio_capacity_report("ses_aio")["verdict"] == "OK"

    # Message count is TELEMETRY: 120 low-context messages report OK and never block.
    busy = tmp_path / "busy.db"
    _canonical_session_db(busy, turns=120, context=1000)
    monkeypatch.setenv("FINOPS_OPENCODE_DB", str(busy))
    assert validate_submit_request(request) == []
    assert sw.aio_capacity_report("ses_aio")["verdict"] == "OK"

    # The native boundary is REPORTED (COMPACT) — and still never blocks the submit.
    boundary = tmp_path / "boundary.db"
    _canonical_session_db(boundary, turns=60, context=970_000)
    monkeypatch.setenv("FINOPS_OPENCODE_DB", str(boundary))
    assert validate_submit_request(request) == []
    report = sw.aio_capacity_report("ses_aio")
    assert report["verdict"] == "COMPACT"
    assert report["advisory"] is True


def test_the_report_consumes_the_shared_override(tmp_path, monkeypatch):
    """The SAME resolution the CLI and capsule consume: FINOPS_SESSION_CTX_LIMIT moves the
    report. A policy cap below the native boundary is a LOCAL POLICY close (never a claimed
    native compaction — reviewer finding) — reported as an advisory, never a refusal."""
    from scripts.fleet import spawn_wrapper as sw

    _capacity_env(tmp_path, monkeypatch)
    db = tmp_path / "override.db"
    _canonical_session_db(db, turns=10, context=120_000)
    request, _ = _valid_bound_request(tmp_path, monkeypatch, db_name=None)
    monkeypatch.setenv("FINOPS_OPENCODE_DB", str(db))
    assert validate_submit_request(request) == []  # 120K < 968K usable
    assert sw.aio_capacity_report("ses_aio")["verdict"] == "OK"
    monkeypatch.setenv("FINOPS_SESSION_CTX_LIMIT", "100000")
    assert validate_submit_request(request) == []
    report = sw.aio_capacity_report("ses_aio")
    assert report["verdict"] == "CLOSE"
    assert "LOCAL POLICY" in report["reason"]


def test_a_completed_compaction_moves_the_report_to_the_post_compaction_state(
    tmp_path, monkeypatch
):
    """Reviewer reproduction, retained as a REPORT regression: after a successful compaction
    (summary + pending resumed turn) the stale 975K reading must not linger — the report
    reads OK/post-compaction. The gate never blocked in either state (2026-09-16 policy)."""
    import json as _json
    import sqlite3 as _sqlite3

    from scripts.fleet import spawn_wrapper as sw

    _capacity_env(tmp_path, monkeypatch)
    db = tmp_path / "compacted.db"
    _canonical_session_db(db, turns=60, context=975_000)
    request, _ = _valid_bound_request(tmp_path, monkeypatch, db_name=None)
    monkeypatch.setenv("FINOPS_OPENCODE_DB", str(db))
    assert validate_submit_request(request) == []
    assert sw.aio_capacity_report("ses_aio")["verdict"] == "COMPACT"

    con = _sqlite3.connect(db)
    con.execute(
        "INSERT INTO message VALUES ('ses_aio', 99000, ?)",
        (_json.dumps({"role": "assistant", "summary": True, "mode": "compaction",
                      "finish": "stop",
                      "tokens": {"total": 975_000, "input": 975_000}}),),
    )
    con.execute(
        "INSERT INTO message VALUES ('ses_aio', 99500, ?)",
        (_json.dumps({"role": "assistant", "tokens": {"total": 0, "input": 0}}),),
    )
    con.commit()
    con.close()
    assert validate_submit_request(request) == []
    report = sw.aio_capacity_report("ses_aio")
    assert report["verdict"] == "OK"
    assert "post-compaction" in report["reason"]


def test_a_pending_only_session_has_no_usable_measurement(tmp_path, monkeypatch):
    """Reviewer finding: a pending, zero-valued sample must NOT read as measured/OK."""
    from scripts.fleet import spawn_wrapper as sw

    db = tmp_path / "pending.db"
    _canonical_session_db(db, pending_only=True)
    monkeypatch.setenv("FINOPS_OPENCODE_DB", str(db))
    report = sw._aio_budget_verdict("ses_aio")
    assert report["verdict"] == "UNJUDGED"
    assert "no usable measurement" in report["reason"]
    # Reachable backend, no usable sample: never a claimed measurement.
    assert report["backend_available"] is True and report["measured"] is False


def test_an_initial_session_is_the_explicit_exception(tmp_path, monkeypatch):
    """A session with no assistant message yet is OK — named as the initial-session case."""
    import sqlite3

    from scripts.fleet import spawn_wrapper as sw

    db = tmp_path / "fresh.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE session (id TEXT, time_updated INTEGER)")
    con.execute("CREATE TABLE message (session_id TEXT, time_created INTEGER, data TEXT)")
    con.execute("INSERT INTO session VALUES ('ses_aio', 200)")
    con.commit()
    con.close()
    monkeypatch.setenv("FINOPS_OPENCODE_DB", str(db))
    report = sw._aio_budget_verdict("ses_aio")
    assert report["verdict"] == "OK" and "initial session" in report["reason"]
    # A NAMED exception, not a measurement: nothing was recorded to measure.
    assert report["backend_available"] is True and report["measured"] is False


# ── The actor declaration must be consistent (reviewer repair) ────────────────


def test_actor_aio_without_a_block_is_refused():
    for extra in ({"actor": "aio"}, {"actor": "aio", "aio": None}):
        errors = validate_submit_request(_valid_submit_request(**extra))
        assert any("requires a complete aio binding block" in e for e in errors), extra


def test_an_aio_block_without_the_actor_is_an_inconsistent_declaration():
    errors = validate_submit_request(
        _valid_submit_request(aio=_aio_block(binding_id="0" * 64))
    )
    assert any("inconsistent declaration" in e for e in errors)


# ── The binding must apply to the submitted work (reviewer repair) ────────────


def test_a_binding_naming_a_foreign_project_is_refused(aio_env):
    binding_id = _bound_store(aio_env, project="some-unrelated-git-project")
    errors = validate_submit_request(_aio_request(aio=_aio_block(binding_id=binding_id)))
    assert any("does not match the submitted project" in e for e in errors)


def _git_project(tmp_path, name: str, origin: str):
    import subprocess

    root = tmp_path / name
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", origin], check=True)
    (root / "README.md").write_text("x")
    git = ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True)
    return root


def test_the_two_project_identities_must_agree(tmp_path):
    """The reviewer repair: a union let a foreign worktree pass when the binding matched
    EITHER side. Both sides are established independently and must share an identity."""
    from scripts.fleet import spawn_wrapper as sw

    proj_a = _git_project(tmp_path, "proj-a", "git@github.com:org/proj-a.git")
    proj_b = _git_project(tmp_path, "proj-b", "git@github.com:org/proj-b.git")
    agreed, errors = sw._project_agreement(proj_a, str(proj_b))
    assert agreed == set()
    assert errors and "DIFFERENT project" in errors[0]


def test_a_linked_worktree_of_the_same_project_agrees(tmp_path):
    """Legitimate linked worktrees are preserved: they share the common git dir identity."""
    import subprocess

    from scripts.fleet import spawn_wrapper as sw

    proj_a = _git_project(tmp_path, "proj-a", "git@github.com:org/proj-a.git")
    worktree = tmp_path / "wt-a"
    subprocess.run(
        ["git", "-C", str(proj_a), "worktree", "add", "-q", str(worktree), "-b", "wt-a"],
        check=True,
    )
    agreed, errors = sw._project_agreement(proj_a, str(worktree))
    assert errors == []
    assert "github.com/org/proj-a" in agreed


def test_both_cross_project_binding_cases_are_refused_before_launch(aio_env, tmp_path):
    """A binding matching EITHER side of two disagreeing repositories must refuse."""
    from scripts.fleet import spawn_wrapper as sw

    proj_a = _git_project(tmp_path, "proj-a", "git@github.com:org/proj-a.git")
    proj_b = _git_project(tmp_path, "proj-b", "git@github.com:org/proj-b.git")
    for project in ("github.com/org/proj-a", "github.com/org/proj-b"):
        binding_id = _bound_store(aio_env, project=project)
        errors = sw._validate_aio_binding(
            _aio_block(binding_id=binding_id), repo_root=proj_a, workdir=str(proj_b),
        )
        assert any("DIFFERENT project" in e for e in errors), project
        for slot in (aio_env / "aio-bindings").glob("*.json"):
            slot.unlink()


def test_a_linked_worktree_accepts_origin_and_canonical_name_bindings(aio_env, tmp_path):
    """The reviewer repair: after agreement is PROVEN via origin/common git dir, the
    established project's aliases stay valid — including its canonical checkout name —
    regardless of the linked worktree's differing directory name."""
    import subprocess

    from scripts.fleet import spawn_wrapper as sw

    proj_a = _git_project(tmp_path, "proj-a", "git@github.com:org/proj-a.git")
    worktree = tmp_path / "wt-a"
    subprocess.run(
        ["git", "-C", str(proj_a), "worktree", "add", "-q", str(worktree), "-b", "wt-a"],
        check=True,
    )
    for project in ("github.com/org/proj-a", "proj-a"):
        binding_id = _bound_store(aio_env, project=project)
        errors = sw._validate_aio_binding(
            _aio_block(binding_id=binding_id), repo_root=proj_a, workdir=str(worktree),
        )
        assert errors == [], project
        for slot in (aio_env / "aio-bindings").glob("*.json"):
            slot.unlink()

    # A foreign project name still refuses on the same linked worktree.
    binding_id = _bound_store(aio_env, project="some-unrelated-project")
    errors = sw._validate_aio_binding(
        _aio_block(binding_id=binding_id), repo_root=proj_a, workdir=str(worktree),
    )
    assert any("does not match the submitted project" in e for e in errors)


DETERMINISTIC_SPEC_YAML = """\
name: deterministic_fixture
question: a deterministic test step, no agent phase
version: "0.1"
artifact_kind: workflow
intent: mutate
side_effects:
  repository: false
  external_services: false
workflow:
  kind: agent_task
  params:
    phases:
      - name: deterministic_check
        kind: test
        timeout: 120
        tests:
          - tests/test_something.py
        prompt: |
          {goal}
factors: []
design: factorial
rules: []
metrics: []
comparison: null
"""

KIND_TASK_SPEC_YAML = """\
name: kind_task_fixture
question: a kind-task phase (the runner's AGENT branch)
version: "0.1"
artifact_kind: workflow
intent: mutate
side_effects:
  repository: false
  external_services: false
workflow:
  kind: agent_task
  params:
    phases:
      - name: deterministic_check
        kind: task
        timeout: 120
        prompt: |
          {goal}
factors: []
design: factorial
rules: []
metrics: []
comparison: null
"""

OMITTED_KIND_SPEC_YAML = """\
name: omitted_kind_fixture
question: a phase with no kind (the runner defaults to agent)
version: "0.1"
artifact_kind: workflow
intent: mutate
side_effects:
  repository: false
  external_services: false
workflow:
  kind: agent_task
  params:
    phases:
      - name: deterministic_check
        timeout: 120
        prompt: |
          {goal}
factors: []
design: factorial
rules: []
metrics: []
comparison: null
"""


class _RecordingAgentExecutor:
    """Records every AGENT-branch invocation (the consequential call the check must prevent)."""

    def __init__(self):
        self.calls: list[str] = []

    def execute(self, request):
        self.calls.append(request.phase_name)
        target = Path(request.workdir) / "work" / f"{request.phase_name}.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x")
        return StepResult(ok=True, state="ok", exit_code=0)


class _RecordingVerifierExecutor:
    def __init__(self):
        self.calls: list[str] = []

    def execute(self, request):
        self.calls.append(request.phase_name)
        return StepResult(
            ok=True, state="ok", exit_code=0, tests_passed=1, tests_total=1,
            test_executed_success=True,
        )


def _load_spec_yaml(tmp_path, name: str, text: str):
    from agentic_dynamics.experiment.experiment_spec import load_spec

    path = tmp_path / name
    path.write_text(text)
    return load_spec(path)


def test_only_test_kinds_are_deterministic_matching_the_runner(tmp_path):
    """The reviewer repair: the runner dispatches EVERY non-test kind to its AGENT branch
    (omitted kind included), so the deterministic check allows only `kind: test`."""
    from scripts.fleet import spawn_wrapper as sw

    deterministic = _load_spec_yaml(tmp_path, "det.yaml", DETERMINISTIC_SPEC_YAML)
    assert sw._deterministic_phase_errors(deterministic) == []

    for name, text in (("task.yaml", KIND_TASK_SPEC_YAML), ("none.yaml", OMITTED_KIND_SPEC_YAML)):
        spec = _load_spec_yaml(tmp_path, name, text)
        errors = sw._deterministic_phase_errors(spec)
        assert errors and "AGENT branch" in errors[0], name

    agentic = load_spec(_REPO_ROOT / _SUBMIT_SPEC)
    errors = sw._deterministic_phase_errors(agentic)
    assert errors and "agent phases" not in errors[0]  # named offender + the branch rule


def test_the_validator_and_the_runner_agree_on_the_deterministic_fixture(tmp_path):
    """Together, through the REAL runner with recording executors: the validator admits the
    `kind: test` fixture AND the runner makes ZERO agent calls executing it."""
    from agentic_dynamics.runtime.workflow_runner import run_workflow
    from scripts.fleet import spawn_wrapper as sw

    spec = _load_spec_yaml(tmp_path, "det.yaml", DETERMINISTIC_SPEC_YAML)
    assert sw._deterministic_phase_errors(spec) == []

    agent = _RecordingAgentExecutor()
    verifier = _RecordingVerifierExecutor()
    workdir = tmp_path / "wd"
    workdir.mkdir()
    result = run_workflow(
        spec, goal="g", model="deepseek/deepseek-v4-flash", workdir=workdir,
        step_executor=agent, verifier_executor=verifier, commit=False, publish=False,
    )
    assert result.ok is True
    assert agent.calls == [], "the deterministic path made an agent call"
    assert verifier.calls == ["deterministic_check"]


def test_a_kind_task_spec_would_take_the_agents_branch(tmp_path):
    """The reviewer reproduction, inverted: `kind: task` is AGENT work — the runner calls the
    agent executor, which is exactly why the deterministic check refuses it."""
    from agentic_dynamics.runtime.workflow_runner import run_workflow
    from scripts.fleet import spawn_wrapper as sw

    spec = _load_spec_yaml(tmp_path, "task.yaml", KIND_TASK_SPEC_YAML)
    assert sw._deterministic_phase_errors(spec)  # refused BEFORE any execution

    agent = _RecordingAgentExecutor()
    verifier = _RecordingVerifierExecutor()
    workdir = tmp_path / "wd"
    workdir.mkdir()
    run_workflow(
        spec, goal="g", model="deepseek/deepseek-v4-flash", workdir=workdir,
        step_executor=agent, verifier_executor=verifier, commit=False, publish=False,
    )
    assert agent.calls == ["deterministic_check"], "kind: task must reach the agent branch"


def test_the_validate_submit_cli_reports_errors_as_json(monkeypatch, capsys):
    """The tool's local-mode gate calls exactly this CLI (stdin request → JSON verdict)."""
    import io
    import json as _json

    from scripts.fleet import spawn_wrapper as sw

    monkeypatch.setattr("sys.stdin", io.StringIO(_json.dumps(_valid_submit_request())))
    assert sw.main(["validate-submit"]) == 0
    ok = _json.loads(capsys.readouterr().out)
    assert ok == {"ok": True, "errors": []}

    monkeypatch.setattr("sys.stdin", io.StringIO(_json.dumps({"spec": "nope.yaml"})))
    assert sw.main(["validate-submit"]) == 2
    bad = _json.loads(capsys.readouterr().out)
    assert bad["ok"] is False and bad["errors"]


def test_a_shared_directory_name_never_overrides_conflicting_origins(tmp_path):
    """The reviewer repair: two unrelated repositories both named ``review-pr76`` must not
    agree on the name — agreement is the canonical origin or the common git dir."""
    from scripts.fleet import spawn_wrapper as sw

    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    repo_a = _git_project(tmp_path / "a", "review-pr76", "git@github.com:org-a/review-pr76.git")
    repo_b = _git_project(tmp_path / "b", "review-pr76", "git@github.com:org-b/review-pr76.git")
    agreed, errors = sw._project_agreement(repo_a, str(repo_b))
    assert agreed == set()
    assert errors and "DIFFERENT project" in errors[0]
    assert "a shared directory name is not shared identity" in errors[0]


def test_a_binding_cannot_ride_the_shared_name_across_projects(aio_env, tmp_path):
    from scripts.fleet import spawn_wrapper as sw

    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    repo_a = _git_project(tmp_path / "a", "review-pr76", "git@github.com:org-a/review-pr76.git")
    repo_b = _git_project(tmp_path / "b", "review-pr76", "git@github.com:org-b/review-pr76.git")
    binding_id = _bound_store(aio_env, project="review-pr76")  # the shared NAME
    errors = sw._validate_aio_binding(
        _aio_block(binding_id=binding_id), repo_root=repo_a, workdir=str(repo_b),
    )
    assert any("DIFFERENT project" in e for e in errors)


# ── Continuation provenance at the real AIO validation boundary (round 4) ─────


def _local_only_repo(tmp_path: Path, name: str) -> Path:
    """A git repo with NO origin remote (the local-only provenance channel)."""
    root = tmp_path / name
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "README.md").write_text("x", encoding="utf-8")
    git = ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True)
    return root


def _clone_provenance(path: Path) -> str:
    """The clone's stamped project provenance ('' when unstamped)."""
    proc = subprocess.run(
        ["git", "-C", str(path), "config", "--get", "agentic-dynamics.project"],
        capture_output=True, text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _continuation_fixture(tmp_path, monkeypatch, canonical: Path, *, stamped: bool = True):
    """A parent run's private clone (with a phase commit) + its ledger + the preparer wired
    in + the submit spec present at the canonical root. Returns (fm, cfg, clone_path).

    ``stamped=False`` builds the PRE-FIX shape by hand: ``git clone`` only (local origin,
    no provenance stamp), exactly how a clone created before the provenance fix looks.
    """
    import importlib
    import sys as _sys

    from agentic_dynamics.runtime.run_clone import create_run_clone

    spec_src = (
        Path(__file__).resolve().parent.parent
        / "workflows" / "repository" / "fleet_job_submission.yaml"
    )
    spec_dst = canonical / "workflows" / "repository" / "fleet_job_submission.yaml"
    spec_dst.parent.mkdir(parents=True, exist_ok=True)
    spec_dst.write_bytes(spec_src.read_bytes())

    runs_root = tmp_path / "runs"
    cfg = PathConfig(
        repo_root=canonical,
        git_dir=canonical / ".git",
        worktrees_root=tmp_path,
        runs_root=runs_root,
        results_dir=tmp_path / "results",
        state_root=tmp_path / "state",
        auth_home=tmp_path / "auth",
    )
    if stamped:
        clone_path = create_run_clone("run-parent", path_config=cfg).path
    else:
        clone_path = runs_root / "run-parent" / "repo"
        clone_path.parent.mkdir(parents=True)
        subprocess.run(
            ["git", "clone", "-q", "--no-hardlinks", "--", str(canonical), str(clone_path)],
            check=True,
        )
    git = ["git", "-C", str(clone_path), "-c", "user.email=t@t", "-c", "user.name=t"]
    (clone_path / "phase.txt").write_text("built", encoding="utf-8")
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "[workflow] build"], check=True)
    candidate = subprocess.run(
        ["git", "-C", str(clone_path), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    ledger_dir = canonical / "experiments" / "results" / "workflows" / "demo"
    ledger_dir.mkdir(parents=True)
    (ledger_dir / "20260916T000000000000Z_run-parent.json").write_text(
        json.dumps({
            "run_id": "run-parent",
            "git_sha": candidate,
            "phases": [{"phase": "build", "status": "ok"}],
        }),
        encoding="utf-8",
    )
    fleet_dir = str(Path(__file__).resolve().parent.parent / "scripts" / "fleet")
    if fleet_dir not in _sys.path:
        _sys.path.insert(0, fleet_dir)
    fm = importlib.import_module("fleet_manager")
    monkeypatch.setenv("FINOPS_RUNS_ROOT", str(runs_root))
    monkeypatch.setattr(fm, "_REPO_ROOT", canonical)
    return fm, cfg, clone_path


def _continuation_request(prepared, binding_id: str) -> dict:
    return _valid_submit_request(
        actor="aio",
        aio=_aio_block(binding_id=binding_id),
        workdir=str(prepared),
        resume=True,
        parent_run_id="run-parent",
    )


def test_a_prepared_continuation_passes_the_aio_boundary_with_an_origin(
    aio_env, tmp_path, monkeypatch
):
    """Reviewer finding (round 4): the continuation workspace is the parent's private clone —
    an independent repo with a local origin path. Through the REAL AIO validation boundary it
    must present the canonical project's identity (via its stamped/aligned provenance), not
    read as a DIFFERENT project."""
    canonical = _git_project(
        tmp_path, "canonical", "git@github.com:peparhugo/agentic-dynamics.git"
    )
    fm, cfg, clone = _continuation_fixture(tmp_path, monkeypatch, canonical)
    prepared, note, errors = fm.prepare_workspace(
        spec="demo", goal="g", model="m", resume=True, parent_run_id="run-parent"
    )
    assert errors == [] and prepared == clone

    binding_id = _bound_store(aio_env)
    validation_errors = validate_submit_request(
        _continuation_request(prepared, binding_id),
        repo_root=canonical,
        path_config=cfg,
    )
    assert validation_errors == [], validation_errors


def test_a_prepared_continuation_passes_the_aio_boundary_local_only(
    aio_env, tmp_path, monkeypatch
):
    """The provenance channel without an origin: a local-only canonical repo's clone carries
    the stamped common git dir and still agrees at the real boundary."""
    canonical = _local_only_repo(tmp_path, "canonical")
    fm, cfg, clone = _continuation_fixture(tmp_path, monkeypatch, canonical)
    prepared, note, errors = fm.prepare_workspace(
        spec="demo", goal="g", model="m", resume=True, parent_run_id="run-parent"
    )
    assert errors == [] and prepared == clone

    binding_id = _bound_store(aio_env)
    validation_errors = validate_submit_request(
        _continuation_request(prepared, binding_id),
        repo_root=canonical,
        path_config=cfg,
    )
    assert validation_errors == [], validation_errors


def test_a_foreign_clone_still_refuses_at_the_aio_boundary(aio_env, tmp_path, monkeypatch):
    """Foreign repositories still refuse: a clone of a DIFFERENT project records the foreign
    provenance and the project check refuses it at the real boundary."""
    from agentic_dynamics.runtime.run_clone import create_run_clone

    canonical = _local_only_repo(tmp_path, "canonical")
    foreign = _git_project(tmp_path, "foreign", "git@github.com:org/foreign.git")
    fm, cfg, clone = _continuation_fixture(tmp_path, monkeypatch, canonical)
    foreign_clone = create_run_clone("run-foreign", source_repo=foreign, path_config=cfg)

    binding_id = _bound_store(aio_env)
    errors = validate_submit_request(
        _valid_submit_request(
            actor="aio",
            aio=_aio_block(binding_id=binding_id),
            workdir=str(foreign_clone.path),
        ),
        repo_root=canonical,
        path_config=cfg,
    )
    assert any("DIFFERENT project" in e for e in errors), errors


def test_a_pre_fix_clone_is_verified_and_stamped_then_passes_the_boundary(
    aio_env, tmp_path, monkeypatch
):
    """Round-5 finding (2026-09-16): a parent clone created BEFORE the provenance stamp
    (local origin, no stamp) must still continue — preparation verifies it by SHARED HISTORY
    and stamps it (candidate commits untouched), and the real AIO boundary then passes."""
    canonical = _git_project(
        tmp_path, "canonical", "git@github.com:peparhugo/agentic-dynamics.git"
    )
    fm, cfg, clone = _continuation_fixture(tmp_path, monkeypatch, canonical, stamped=False)
    # The fixture really is the pre-fix shape: local origin, no provenance stamp.
    assert _clone_provenance(clone) == ""

    prepared, note, errors = fm.prepare_workspace(
        spec="demo", goal="g", model="m", resume=True, parent_run_id="run-parent"
    )
    assert errors == [] and prepared == clone
    # Verified and stamped at preparation — the stamp now carries the canonical identity.
    assert _clone_provenance(clone) != ""

    binding_id = _bound_store(aio_env)
    validation_errors = validate_submit_request(
        _continuation_request(prepared, binding_id),
        repo_root=canonical,
        path_config=cfg,
    )
    assert validation_errors == [], validation_errors


def test_a_foreign_pre_fix_clone_is_never_stamped(aio_env, tmp_path, monkeypatch):
    """The pre-fix verification preserves the foreign-project check: a clone of an unrelated
    repository shares no history with the canonical one, refuses — and is never stamped.

    The foreign fixture gets a genuinely DIFFERENT root commit (distinct content + message):
    git identity is content-addressed, so fixtures that happen to produce bit-identical
    roots would be the same lineage by git's own model.
    """
    canonical = _local_only_repo(tmp_path, "canonical")
    fm, cfg, _clone = _continuation_fixture(tmp_path, monkeypatch, canonical)

    foreign = tmp_path / "foreign"
    foreign.mkdir()
    subprocess.run(["git", "init", "-q", str(foreign)], check=True)
    (foreign / "different.txt").write_text("foreign-only", encoding="utf-8")
    git = ["git", "-C", str(foreign), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "foreign root"], check=True)

    foreign_clone = cfg.runs_root / "run-foreign" / "repo"
    foreign_clone.parent.mkdir(parents=True)
    subprocess.run(
        ["git", "clone", "-q", "--no-hardlinks", "--", str(foreign), str(foreign_clone)],
        check=True,
    )
    errors = fm._ensure_clone_provenance(foreign_clone, canonical)
    assert any("DIFFERENT repository" in e for e in errors), errors
    assert _clone_provenance(foreign_clone) == ""


def _fork_of(canonical: Path, tmp_path: Path, name: str, url: str) -> Path:
    """A clone of ``canonical`` with a FORK's origin (shared history, different project)."""
    fork = tmp_path / name
    subprocess.run(
        ["git", "clone", "-q", "--no-hardlinks", "--", str(canonical), str(fork)], check=True
    )
    subprocess.run(["git", "-C", str(fork), "remote", "set-url", "origin", url], check=True)
    (fork / "fork-only.txt").write_text("fork", encoding="utf-8")
    git = ["git", "-C", str(fork), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "fork change"], check=True)
    return fork


def test_a_foreign_fork_with_shared_history_is_never_stamped(aio_env, tmp_path, monkeypatch):
    """Round-6 finding (2026-09-16): a FORK shares the canonical root commit but has its own
    origin. Preparation must NOT stamp it — the explicit origin conflict refuses first, and
    shared ancestry may only corroborate a relationship, never establish identity."""
    canonical = _git_project(
        tmp_path, "canonical", "git@github.com:peparhugo/agentic-dynamics.git"
    )
    fm, cfg, _clone = _continuation_fixture(tmp_path, monkeypatch, canonical)
    fork = _fork_of(canonical, tmp_path, "fork", "git@github.com:other/agentic-dynamics.git")

    # A pre-fix clone OF THE FORK: shared root history, origin = the fork's local path.
    fork_clone = cfg.runs_root / "run-fork" / "repo"
    fork_clone.parent.mkdir(parents=True)
    subprocess.run(
        ["git", "clone", "-q", "--no-hardlinks", "--", str(fork), str(fork_clone)],
        check=True,
    )
    head = subprocess.run(
        ["git", "-C", str(fork_clone), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    assert fm._shares_root(fork_clone, canonical)  # the regression's precondition

    # Direct verification: refused, never stamped.
    errors = fm._ensure_clone_provenance(fork_clone, canonical, parent_run_id="run-fork")
    assert any("DIFFERENT repository" in e for e in errors), errors
    assert _clone_provenance(fork_clone) == ""

    # Through PREPARATION: the fork clone + its ledger refuses (and stays unstamped).
    ledger_dir = canonical / "experiments" / "results" / "workflows" / "demo"
    (ledger_dir / "20260916T000000000000Z_run-fork.json").write_text(
        json.dumps({"run_id": "run-fork", "git_sha": head,
                    "phases": [{"phase": "build", "status": "ok"}]}),
        encoding="utf-8",
    )
    prepared, _note, prep_errors = fm.prepare_workspace(
        spec="demo", goal="g", model="m", resume=True, parent_run_id="run-fork"
    )
    assert prepared is None and prep_errors
    assert _clone_provenance(fork_clone) == ""

    # And the full submission validator still refuses it (no stamp was written).
    binding_id = _bound_store(aio_env)
    validation_errors = validate_submit_request(
        _valid_submit_request(
            actor="aio", aio=_aio_block(binding_id=binding_id), workdir=str(fork_clone),
        ),
        repo_root=canonical,
        path_config=cfg,
    )
    assert any("DIFFERENT project" in e for e in validation_errors), validation_errors


def test_a_container_local_repo_origin_is_established_by_record_and_mapping(
    aio_env, tmp_path, monkeypatch
):
    """The legacy container-local case (retained from round 5): a pre-fix clone whose origin
    is ``/repo`` (the compose mount view). The run/source relationship — run-clone path +
    run id — establishes it, shared ancestry corroborates, and the real boundary passes."""
    # The container view must not be a GIT repository on this host, or the resolved-path
    # branch (correctly) takes precedence over the container-view channel.
    assert not (Path("/repo") / ".git").exists(), "the container view must not be a repo here"
    canonical = _git_project(
        tmp_path, "canonical", "git@github.com:peparhugo/agentic-dynamics.git"
    )
    fm, cfg, clone = _continuation_fixture(tmp_path, monkeypatch, canonical, stamped=False)
    subprocess.run(
        ["git", "-C", str(clone), "remote", "set-url", "origin", "/repo"], check=True
    )
    assert _clone_provenance(clone) == ""

    errors = fm._ensure_clone_provenance(clone, canonical, parent_run_id="run-parent")
    assert errors == [], errors
    assert _clone_provenance(clone) != ""

    binding_id = _bound_store(aio_env)
    validation_errors = validate_submit_request(
        _continuation_request(clone, binding_id),
        repo_root=canonical,
        path_config=cfg,
    )
    assert validation_errors == [], validation_errors


def test_a_two_step_local_origin_chain_resolves_to_the_canonical_identity(
    tmp_path, monkeypatch
):
    """A local-path origin chain (a clone of a clone of the canonical repo) resolves through
    to the project URL — accepted with the canonical stamp. A fork anywhere in the chain
    would end at the fork's URL and refuse (the fork test above)."""
    canonical = _git_project(
        tmp_path, "canonical", "git@github.com:peparhugo/agentic-dynamics.git"
    )
    fm, cfg, _clone = _continuation_fixture(tmp_path, monkeypatch, canonical)
    intermediate = tmp_path / "intermediate"
    subprocess.run(
        ["git", "clone", "-q", "--no-hardlinks", "--", str(canonical), str(intermediate)],
        check=True,
    )
    chained = cfg.runs_root / "run-chain" / "repo"
    chained.parent.mkdir(parents=True)
    subprocess.run(
        ["git", "clone", "-q", "--no-hardlinks", "--", str(intermediate), str(chained)],
        check=True,
    )
    errors = fm._ensure_clone_provenance(chained, canonical, parent_run_id="run-chain")
    assert errors == [], errors
    assert _clone_provenance(chained) != ""


def test_a_stale_canonical_stamp_never_overrides_a_foreign_remote_origin(
    aio_env, tmp_path, monkeypatch
):
    """Round-7 finding (2026-09-16): the PREVIOUS ancestry-only upgrader could write a
    canonical provenance stamp onto a fork clone. An explicitly conflicting REMOTE origin
    must defeat that stale stamp — in preparation AND at the submission validator."""
    canonical = _git_project(
        tmp_path, "canonical", "git@github.com:peparhugo/agentic-dynamics.git"
    )
    fm, cfg, _clone = _continuation_fixture(tmp_path, monkeypatch, canonical)

    # The contradictory artifact: a clone of the canonical whose ORIGIN names the fork,
    # carrying the stale canonical stamp the previous upgrader wrote.
    fork_stamped = cfg.runs_root / "run-fork" / "repo"
    fork_stamped.parent.mkdir(parents=True)
    subprocess.run(
        ["git", "clone", "-q", "--no-hardlinks", "--", str(canonical), str(fork_stamped)],
        check=True,
    )
    stale = "origin:git@github.com:peparhugo/agentic-dynamics.git"
    subprocess.run(
        ["git", "-C", str(fork_stamped), "remote", "set-url", "origin",
         "git@github.com:other/agentic-dynamics.git"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(fork_stamped), "config", "agentic-dynamics.project", stale],
        check=True,
    )
    assert _clone_provenance(fork_stamped) == stale  # the contradictory state, reproduced

    # 1) Preparation refuses DESPITE the stamp.
    errors = fm._ensure_clone_provenance(fork_stamped, canonical, parent_run_id="run-fork")
    assert errors and "CONFLICTS" in errors[0], errors

    # 2) The submission validator refuses DESPITE the stamp.
    binding_id = _bound_store(aio_env)
    validation_errors = validate_submit_request(
        _valid_submit_request(
            actor="aio", aio=_aio_block(binding_id=binding_id), workdir=str(fork_stamped),
        ),
        repo_root=canonical,
        path_config=cfg,
    )
    assert any("DIFFERENT project" in e for e in validation_errors), validation_errors


def test_a_foreign_local_origin_with_a_stale_stamp_refuses_the_broker_dry_run(
    aio_env, tmp_path, monkeypatch
):
    """Round-8 finding (2026-09-16): an explicit --workdir skips preparation, so the SHARED
    identity rule must reach the same verdict as preparation — a local origin pointing at a
    foreign fork with a stale canonical stamp refuses in the validator AND in the broker's
    explicit-workdir dry run (the reviewer's `ok: true` surface)."""
    import launch_broker

    canonical = _git_project(
        tmp_path, "canonical", "git@github.com:peparhugo/agentic-dynamics.git"
    )
    fork = _git_project(tmp_path, "fork-src", "git@github.com:other/agentic-dynamics.git")
    fm, cfg, _clone = _continuation_fixture(tmp_path, monkeypatch, canonical)

    # A canonical-derived clone whose ORIGIN is the fork's LOCAL path (the worktree shares
    # canonical history — the reviewer's bypass shape) + the stale canonical stamp.
    workdir = cfg.runs_root / "run-fork" / "repo"
    workdir.parent.mkdir(parents=True)
    subprocess.run(
        ["git", "clone", "-q", "--no-hardlinks", "--", str(canonical), str(workdir)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(workdir), "remote", "set-url", "origin", str(fork)], check=True
    )
    stale = "origin:git@github.com:peparhugo/agentic-dynamics.git"
    subprocess.run(
        ["git", "-C", str(workdir), "config", "agentic-dynamics.project", stale], check=True
    )

    # The SHARED rule follows the local origin chain: conflict.
    from scripts.fleet import broker_contract as bc

    verdict, detail = bc.identity_verdict(canonical, workdir)
    assert verdict == "conflict", (verdict, detail)

    # 1) Explicit-workdir validation refuses despite the stamp.
    binding_id = _bound_store(aio_env)
    errors = validate_submit_request(
        _valid_submit_request(
            actor="aio", aio=_aio_block(binding_id=binding_id), workdir=str(workdir),
        ),
        repo_root=canonical,
        path_config=cfg,
    )
    assert any("DIFFERENT project" in e for e in errors), errors

    # 2) The SAME workspace through AUTOMATIC preparation refuses too (equivalence).
    head = subprocess.run(
        ["git", "-C", str(workdir), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    ledger_dir = canonical / "experiments" / "results" / "workflows" / "demo"
    (ledger_dir / "20260916T000000000000Z_run-fork.json").write_text(
        json.dumps({"run_id": "run-fork", "git_sha": head,
                    "phases": [{"phase": "build", "status": "ok"}]}),
        encoding="utf-8",
    )
    prepared, _note, prep_errors = fm.prepare_workspace(
        spec="demo", goal="g", model="m", resume=True, parent_run_id="run-fork"
    )
    assert prepared is None and prep_errors

    # 3) The BROKER's explicit-workdir dry run refuses (not `ok: true`).
    monkeypatch.setattr(launch_broker, "admission_required", lambda: False)
    command = {
        "action": "submit",
        "job_id": "abcdef123456",
        "spec": "workflows/repository/fleet_job_submission.yaml",
        "goal": "g",
        "model": "anthropic/claude-sonnet-5",
        "workdir": str(workdir),
        "ts": 0.0,
        "nonce": "0" * 12,
        "actor": "aio",
        "aio": {
            "native_session_id": "ses_aio",
            "agent": "aio-control",
            "binding_id": binding_id,
            "task_revision": 1,
        },
    }
    with pytest.raises(launch_broker.LaunchRequestError) as exc:
        launch_broker.submit_run(
            command, repo_root=canonical, path_config=cfg, dry_run=True
        )
    assert "DIFFERENT project" in str(exc.value)


def test_the_shared_identity_rule_covers_the_verdict_channels(tmp_path):
    """The ONE rule both preparation and the validator call: same git dir / equal remote /
    followed local chain → match; conflicting remote / a chain to a foreign origin →
    conflict; unresolvable or missing origin → unknown (the stamp's evidence decides)."""
    from scripts.fleet import broker_contract as bc

    canonical = _git_project(tmp_path, "canonical", "git@github.com:org/proj.git")

    # A LINKED WORKTREE of the canonical: same common git dir → match.
    wt = tmp_path / "wt"
    subprocess.run(
        ["git", "-C", str(canonical), "worktree", "add", "-q", str(wt), "-b", "wt-branch"],
        check=True,
    )
    assert bc.identity_verdict(canonical, wt)[0] == "match"

    # An EQUAL remote origin → match; a conflicting remote → conflict.
    same = tmp_path / "same"
    subprocess.run(
        ["git", "clone", "-q", "--no-hardlinks", "--", str(canonical), str(same)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(same), "remote", "set-url", "origin",
         "git@github.com:org/proj.git"],
        check=True,
    )
    assert bc.identity_verdict(canonical, same)[0] == "match"
    subprocess.run(
        ["git", "-C", str(same), "remote", "set-url", "origin",
         "git@github.com:other/proj.git"],
        check=True,
    )
    assert bc.identity_verdict(canonical, same)[0] == "conflict"

    # A local origin chain: to the canonical → match; redirected to a fork → conflict.
    chain = tmp_path / "chain"
    subprocess.run(
        ["git", "clone", "-q", "--no-hardlinks", "--", str(canonical), str(chain)],
        check=True,
    )
    assert bc.identity_verdict(canonical, chain)[0] == "match"  # origin = canonical path
    fork = _git_project(tmp_path, "fork-src", "git@github.com:other/proj-fork.git")
    subprocess.run(
        ["git", "-C", str(chain), "remote", "set-url", "origin", str(fork)], check=True
    )
    assert bc.identity_verdict(canonical, chain)[0] == "conflict"

    # An unresolvable local origin (the container view) and a missing origin → unknown.
    subprocess.run(
        ["git", "-C", str(chain), "remote", "set-url", "origin", "/repo"], check=True
    )
    assert bc.identity_verdict(canonical, chain)[0] == "unknown"
    subprocess.run(["git", "-C", str(chain), "remote", "remove", "origin"], check=True)
    assert bc.identity_verdict(canonical, chain)[0] == "unknown"
