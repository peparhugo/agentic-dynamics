"""Tests for the launch broker (fleet_launch_boundary b3_launch_broker).

The load-bearing guarantee this suite must catch: after b3, the Docker socket is NOT mounted
into any container, and the launch broker (scripts/fleet/launch_broker.py) is the ONLY Docker
API caller — it accepts ONLY a typed LaunchRequest {image_digest, network, mount_profile,
state_namespace, command, timeout_seconds}, validates it against the fixed mount profiles, and
performs the docker call itself. A raw docker command string, an unknown mount_profile, an
out-of-namespace image, or a request the wrapper's own scope model would refuse NEVER reaches
the socket.

VERIFY coverage (the wave's b3 checklist):

    (a) the broker refuses an untyped/arbitrary request — a raw docker command string is
        rejected, the typed contract holds;
    (b) the broker validates mount_profile against the fixed profiles — an unknown profile
        refuses;
    (c) the broker invokes docker ONLY through its typed path — the only docker argv/call
        sites in the fleet runtime code are inside launch_broker.py;
    (d) spawn_wrapper contains NO docker invocation after the change (source scan);
    (e) the compose no longer mounts the socket into a container (grep the yml);
    (f) the existing spawn-contract tests stay green — the validation shared between wrapper
        and broker keeps the same refusals (the broker re-runs the wrapper's scope checks).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FLEET_DIR = str(_REPO_ROOT / "scripts" / "fleet")
if _FLEET_DIR not in sys.path:
    sys.path.insert(0, _FLEET_DIR)

from scripts.fleet import launch_broker, spawn_wrapper  # noqa: E402

#: A phase authorized for the implementation scope (PHASE_SCOPE_AUTHORIZATION) so builder-made
#: requests validate through the scope model too.
_PHASE = {"name": "p1_slice1_base_supervisor", "scope": "implementation"}


def _built_request(**overrides) -> dict:
    """A real builder-produced typed request (valid for the wrapper AND the broker)."""
    request = spawn_wrapper.build_phase_request(
        _PHASE,
        goal="g",
        workdir="/tmp/wt",
        model="m",
        spec_name="spec_x",
        image="fleet/base",
    )
    request.update(overrides)
    return request


def _default_cfg():
    return spawn_wrapper.default_path_config()


# ── (a) the typed contract holds — an arbitrary/untyped request refuses ──────


def test_broker_refuses_a_raw_docker_command_string():
    """A raw docker command string is NOT a typed request — the typed contract holds."""
    with pytest.raises(launch_broker.LaunchRequestError) as exc:
        launch_broker.launch("docker run --rm -it ubuntu bash")
    assert any("typed launch request" in e and "raw docker command" in e for e in exc.value.errors)


def test_broker_refuses_a_non_mapping_payload():
    for payload in (None, 42, ["docker", "run", "ubuntu"]):
        with pytest.raises(launch_broker.LaunchRequestError):
            launch_broker.launch(payload)


def test_broker_refuses_an_arbitrary_payload_dict():
    """An arbitrary dict (a docker-run argv smuggled as a dict) is refused — the field set is
    closed, so an unknown/foreign field can never be interpreted as a launch."""
    request = {"docker": "run", "args": ["--privileged", "-v", "/:/host"]}
    with pytest.raises(launch_broker.LaunchRequestError) as exc:
        launch_broker.launch(request)
    assert any("unknown field" in e for e in exc.value.errors)


def test_broker_refuses_a_typed_request_missing_a_canonical_field():
    request = _built_request()
    for field in ("image_digest", "mount_profile", "state_namespace", "command", "network"):
        stripped = {k: v for k, v in request.items() if k != field}
        errors = launch_broker.validate_launch_request(stripped)
        assert any("missing the typed field" in e and field in e for e in errors), field


# ── (b) mount_profile is validated against the fixed profiles ───────────────


def test_broker_refuses_an_unknown_mount_profile():
    request = _built_request(mount_profile="hypervisor_root")
    errors = launch_broker.validate_launch_request(request)
    assert any("not one of the fixed profiles" in e for e in errors)


def test_every_fixed_mount_profile_is_accepted_for_a_consistent_request():
    # implementation scope (results rw) ⇒ implementation_rw; results-ro scope ⇒ repo_readonly.
    assert launch_broker.validate_launch_request(_built_request()) == []
    ro_request = spawn_wrapper.build_phase_request(
        {"name": "p1_research_infra", "scope": "research_readonly"},
        goal="g", workdir="/tmp/wt", model="m", spec_name="spec_x", image="fleet/base",
    )
    assert ro_request["mount_profile"] == "repo_readonly"
    assert launch_broker.validate_launch_request(ro_request) == []


def test_a_verifier_request_must_carry_the_verifier_profile():
    agent_request = _built_request(**{spawn_wrapper.VERIFIER_REQUEST_MARKER: True})
    errors = launch_broker.validate_launch_request(agent_request)
    assert any("verifier profile" in e for e in errors)

    verifier_request = _built_request(
        mount_profile="verifier_readonly", **{spawn_wrapper.VERIFIER_REQUEST_MARKER: True},
    )
    assert launch_broker.validate_launch_request(verifier_request) == []


def test_an_agent_request_cannot_carry_the_verifier_profile():
    errors = launch_broker.validate_launch_request(_built_request(mount_profile="verifier_readonly"))
    assert any("verifier-only" in e for e in errors)


def test_profile_results_mode_must_match_the_scope():
    # implementation (results rw) with the results-ro profile refuses: the profile and the
    # scope's writability cannot disagree.
    errors = launch_broker.validate_launch_request(_built_request(mount_profile="repo_readonly"))
    assert any("results_mode" in e and "scope" in e for e in errors)


def test_broker_mounts_from_the_profile_never_a_caller_mount_list():
    """The broker derives the -v flags from ITS OWN profile expansion (mounts_for_profile),
    never from a caller-supplied mount list — a forged mount cannot reach the socket."""
    request = _built_request(command=["python3", "-c", "pass"])
    outcome = launch_broker.launch(request, dry_run=True, path_config=_default_cfg())
    argv = outcome["argv"]
    joined = " ".join(argv)
    mounts = launch_broker.mounts_for_profile(
        request["mount_profile"],
        path_config=_default_cfg(),
        state_namespace=request["state_namespace"],
    )
    for m in mounts:
        assert f"-v {m['source']}:{m['target']}:{m['mode']}" in joined
    # the implementation profile surface is there (rw results + the state namespace), never a
    # bare "/" bind.
    assert "/app/experiments/results:rw" in joined
    assert "-v /:/" not in joined


# ── the broker's typed field checks (image / network / namespace / command / timeout) ──


def test_broker_refuses_an_image_outside_the_closed_namespace():
    request = _built_request(image_digest="docker.io/library/ubuntu:latest")
    errors = launch_broker.validate_launch_request(request)
    assert any("closed fleet image namespace" in e for e in errors)


def test_broker_accepts_fleet_and_job_images():
    for image in ("fleet/base", "fleet/orchestrator", "fleet/supervisor", "fleet/job-example"):
        assert launch_broker.validate_launch_request(_built_request(image_digest=image)) == []


def test_broker_refuses_a_network_other_than_fleet_net():
    errors = launch_broker.validate_launch_request(_built_request(network="host"))
    assert any("network" in e and "fleet-net" in e for e in errors)


def test_broker_refuses_a_state_namespace_escape():
    request = _built_request(state_namespace="../../etc")
    errors = launch_broker.validate_launch_request(request)
    assert any("state_namespace" in e and "safe relative path" in e for e in errors)
    assert launch_broker.validate_launch_request(
        _built_request(state_namespace="run-a/phase-1")
    ) == []


def test_broker_refuses_a_shell_string_or_flag_command():
    shell = _built_request(command="python3 -c 'print(1)'")
    assert any("command must be a non-empty list" in e
               for e in launch_broker.validate_launch_request(shell))
    flag = _built_request(command=["--privileged", "bash"])
    assert any("starts with '-'" in e for e in launch_broker.validate_launch_request(flag))
    newline = _built_request(command=["python3", "-c", "pass\nprint(2)"])
    assert any("argv smuggling" in e for e in launch_broker.validate_launch_request(newline))


def test_broker_refuses_an_out_of_bounds_timeout():
    assert any("timeout_seconds" in e
               for e in launch_broker.validate_launch_request(_built_request(timeout_seconds=-5)))
    assert any("timeout_seconds" in e
               for e in launch_broker.validate_launch_request(
                   _built_request(timeout_seconds=10 ** 9)))


def test_broker_validates_the_run_clone_reference_under_the_runs_root(tmp_path):
    cfg = spawn_wrapper.PathConfig.from_env(require_existing=False)
    good_clone = cfg.runs_root / "run-abc" / "repo"
    errors = launch_broker.validate_launch_request(_built_request(run_clone=str(good_clone)))
    assert errors == []
    for bad in ("/etc/passwd", str(cfg.runs_root / "run-abc" / "other")):
        errors = launch_broker.validate_launch_request(_built_request(run_clone=bad))
        assert errors, bad


# ── fb1_clone_mounted — the broker mounts the run clone as the cell's repo ─────


def test_agent_profile_with_a_run_clone_mounts_the_clone_and_no_shared_surface():
    """(fb1) the broker's own profile expansion — the mounts it will ACTUALLY execute — sources
    the cell's repo from the run clone when the request names one: /repo binds
    runs_root/<run-id>/repo (rw for a commit-capable implementation cell), and the shared
    worktree / .git surface (worktrees_root -> /tmp, the /repo/.git overlay, the D-16 host-path
    repo + .git aliases) is absent from the expansion."""
    cfg = _default_cfg()
    clone = cfg.runs_root / "run-impl" / "repo"
    mounts = launch_broker.mounts_for_profile(
        "implementation_rw",
        path_config=cfg,
        state_namespace="spec_x/p1",
        run_clone=str(clone),
    )
    by_target = {m["target"]: m for m in mounts}
    assert by_target["/repo"]["source"] == str(clone)
    assert by_target["/repo"]["mode"] == "rw"
    assert cfg.runs_root in Path(by_target["/repo"]["source"]).parents
    # the shared surfaces are GONE from the expansion
    assert "/tmp" not in by_target
    assert "/repo/.git" not in by_target
    assert str(cfg.repo_root) not in by_target
    assert str(cfg.git_dir) not in by_target
    sources = {m["source"] for m in mounts}
    assert str(cfg.worktrees_root) not in sources
    assert str(cfg.git_dir) not in sources
    # the rest of the agent-cell surface is unchanged (results + auth + state + credential)
    assert "/app/experiments/results" in by_target
    assert launch_broker.STATE_TARGET in by_target
    assert "/auth/opencode_auth.json" in by_target


def test_readonly_agent_profile_with_a_run_clone_mounts_the_clone_ro():
    cfg = _default_cfg()
    clone = cfg.runs_root / "run-ro" / "repo"
    mounts = launch_broker.mounts_for_profile(
        "repo_readonly",
        path_config=cfg,
        state_namespace="spec_x/p1",
        run_clone=str(clone),
    )
    repo = [m for m in mounts if m["target"] == "/repo"]
    assert len(repo) == 1 and repo[0]["source"] == str(clone) and repo[0]["mode"] == "ro"
    assert not any(m["target"] in ("/tmp", "/repo/.git") for m in mounts)


def test_verifier_profile_with_a_run_clone_mounts_the_clone_read_only():
    """(fb1 VERIFY e, broker half) the verifier profile expansion for a run clone is the
    clone itself, READ-ONLY, and nothing else — no shared worktree/.git, no results/state/auth."""
    cfg = _default_cfg()
    clone = cfg.runs_root / "run-verify" / "repo"
    mounts = launch_broker.mounts_for_profile(
        "verifier_readonly",
        path_config=cfg,
        state_namespace="verifier",
        run_clone=str(clone),
    )
    assert mounts == [{"source": str(clone), "target": "/repo", "mode": "ro"}]


def test_legacy_profile_expansion_is_unchanged_without_a_run_clone():
    """(fb1) WITHOUT a run clone the broker's expansion is byte-identical to the pre-fb1
    shared-worktree shape — the shared /tmp + .git overlays remain for the legacy contract."""
    cfg = _default_cfg()
    mounts = launch_broker.mounts_for_profile(
        "implementation_rw", path_config=cfg, state_namespace="spec_x/p1",
    )
    by_target = {m["target"]: m for m in mounts}
    assert by_target["/tmp"]["source"] == str(cfg.worktrees_root)
    assert by_target["/repo"]["source"] == str(cfg.repo_root)
    assert by_target["/repo/.git"]["source"] == str(cfg.git_dir)
    assert by_target[str(cfg.repo_root)]["mode"] == "ro"  # D-16 host-path alias
    assert by_target[str(cfg.git_dir)]["mode"] == "rw"


def test_broker_launch_argv_for_a_clone_request_mounts_the_clone_only(tmp_path):
    """(fb1) a broker launch of a clone-world request derives its -v flags from the clone
    expansion — the argv mounts the run clone at /repo and carries no shared /tmp or .git bind."""
    cfg = _default_cfg()
    clone = cfg.runs_root / "run-z" / "repo"
    request = spawn_wrapper.build_phase_request(
        _PHASE,
        goal="g",
        workdir="/tmp/wt",
        model="m",
        spec_name="spec_x",
        image="fleet/base",
        run_clone=str(clone),
    )
    outcome = launch_broker.launch(request, dry_run=True, path_config=cfg)
    joined = " ".join(outcome["argv"])
    assert f"-v {clone}:/repo:rw" in joined
    assert f"-v {cfg.worktrees_root}:" not in joined
    assert ":/tmp:rw" not in joined and ":/repo/.git:" not in joined
    assert str(cfg.git_dir) not in joined


# ── (f) the shared validation keeps the same refusals ────────────────────────


def test_broker_re_runs_the_wrappers_scope_model_and_keeps_the_same_refusal():
    """The broker validates what it will execute with the SAME checks the wrapper ran — a
    scope-model violation (e.g. an unauthorized phase) refuses at the broker with the same
    step message, before any docker argv is built."""
    request = _built_request(phase="p6_adversarial", scope="implementation")
    with pytest.raises(launch_broker.LaunchRequestError) as exc:
        launch_broker.launch(request, dry_run=True)
    assert any("step 2" in e and "not authorized" in e for e in exc.value.errors)


def test_wrapper_and_broker_validate_with_the_same_profile_table():
    """The wrapper validates what it intends to submit with validate_launch_request — the SAME
    shared function the broker runs — so the refusals cannot drift between the two sides."""
    bad = _built_request(mount_profile="nope")
    wrapper_errors = spawn_wrapper.validate_launch_request(bad)
    broker_errors = launch_broker.validate_launch_request(bad)
    assert wrapper_errors == broker_errors
    assert any("not one of the fixed profiles" in e for e in broker_errors)


# ── (c) the broker is the ONLY docker call site in the runtime code ──────────

# The docker-argv/call markers that constitute "invoking docker": constructing the ``docker
# run`` argv, the ``docker compose`` argv, and the subprocess that runs them. After b3 these
# may appear in exactly ONE fleet module — the broker.
_DOCKER_CALL_MARKERS = (
    'argv = [docker, "run"',
    'argv = [compose, "-f"',
    '"docker", "run", "--rm"',
    "'docker', 'run', '--rm'",
)


def _fleet_py_sources() -> dict[str, str]:
    return {
        p.name: p.read_text()
        for p in (_REPO_ROOT / "scripts" / "fleet").glob("*.py")
        if p.name != "__init__.py"
    }


def test_only_launch_broker_contains_a_docker_call_site():
    holders = {
        name
        for name, src in _fleet_py_sources().items()
        if any(marker in src for marker in _DOCKER_CALL_MARKERS)
    }
    assert holders == {"launch_broker.py"}, (
        f"the ONLY docker call site must be inside the launch broker, got {sorted(holders)}"
    )


def test_no_runtime_code_outside_scripts_fleet_invokes_docker():
    """The launch surface is the fleet runtime: scanning the top-level scripts + src too, the
    docker-argv markers appear in NO runtime module — the one exception is the IMMUTABLE
    one-time archive (scripts/archive/backfill_sonar.py, a frozen historical migration that is
    never re-run), which is not part of the launch boundary."""
    runtime_dirs = [_REPO_ROOT / "scripts", _REPO_ROOT / "src"]
    hits = []
    for base in runtime_dirs:
        for p in base.rglob("*.py"):
            if "__pycache__" in str(p) or "fleet" in p.parts or "archive" in p.parts:
                continue
            src = p.read_text()
            found = [m for m in _DOCKER_CALL_MARKERS if m in src]
            if found:
                hits.append((str(p.relative_to(_REPO_ROOT)), found))
    assert hits == [], f"docker argv construction outside the broker: {hits}"


def test_launch_broker_does_invoke_docker_through_its_typed_path():
    src = _fleet_py_sources()["launch_broker.py"]
    assert any(marker in src for marker in _DOCKER_CALL_MARKERS)
    # ... and only inside the typed path: no unbounded docker/compose argv in the module.
    assert "def launch(" in src and "def run_fleet_command(" in src


# ── (d) spawn_wrapper contains NO docker invocation ──────────────────────────


def test_spawn_wrapper_contains_no_docker_invocation():
    src = _fleet_py_sources()["spawn_wrapper.py"]
    assert not any(marker in src for marker in _DOCKER_CALL_MARKERS)
    assert "import subprocess" not in src
    # the wrapper's docker-touching entry points delegate to the broker (no argv builders).
    assert "launch_broker.launch" in src
    assert "launch_broker.run_fleet_command" in src
    assert "def build_spawn_argv" not in src
    assert "def build_submit_argv" not in src


# ── (e) the compose no longer mounts the socket into a container ─────────────


def test_compose_contains_no_socket_mount():
    compose = (_REPO_ROOT / "infrastructure" / "docker-compose.ladder.yml").read_text()
    assert "/var/run/docker.sock" not in compose, (
        "the compose must not mount the docker socket into any container (b3 hard rule 1: "
        "the socket leaves the container — the host-side broker owns it)"
    )
    assert "docker.sock" not in compose


# ── the broker CLI (host-side process) shares the same refusals ──────────────


def test_broker_cli_refuses_a_raw_docker_command(capsys):
    rc = launch_broker.main(["launch", "--request", json.dumps({"raw": "docker run ubuntu"})])
    captured = capsys.readouterr()
    assert rc == 2
    assert "typed contract is closed" in captured.err or "unknown field" in captured.err


def test_broker_cli_dry_run_prints_the_typed_argv(capsys):
    request = _built_request(command=["python3", "-c", "pass"])
    rc = launch_broker.main(["launch", "--request", json.dumps(request), "--dry-run"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["argv"][0] == "docker" and "run" in payload["argv"]
