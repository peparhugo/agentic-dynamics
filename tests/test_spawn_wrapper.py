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
    phase_scope,
    validate_spec,
)
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
