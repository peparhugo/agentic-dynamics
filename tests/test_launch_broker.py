"""Tests for the launch broker (fleet_launch_boundary b3_launch_broker).

The load-bearing guarantee this suite must catch: after b3, the Docker socket is NOT mounted
into any container, and the launch broker (scripts/fleet/launch_broker.py) is the ONLY Docker
API caller (its one documented exception — the game board's read-only docker ps in
scripts/system_snapshot.py, fb3 f4, never a launch) — it accepts ONLY a typed LaunchRequest
{image_digest, network, mount_profile,
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


def _scratch_host_cfg(tmp_path):
    """A hermetic HOST-view PathConfig (a scratch repo under ``tmp_path``), like the wrapper
    suite's ``_make_config_repo`` — no dependence on the real checkout or the host env."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "experiments" / "results").mkdir(parents=True)
    auth = tmp_path / "auth"
    (auth / ".local" / "share" / "opencode").mkdir(parents=True)
    return spawn_wrapper.PathConfig(
        repo_root=repo,
        git_dir=repo / ".git",
        worktrees_root=tmp_path / "worktrees",
        runs_root=tmp_path / "runs",
        results_dir=repo / "experiments" / "results",
        state_root=tmp_path / "state",
        auth_home=auth,
    )


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


# ── ws2_broker_pathview — the broker validates the view it executes ──────────
#
# fleet_launch_smoke ws2: a launch request carries the VIEW (host | container) of the
# PathConfig its mounts were built against. A container-tier caller derives a config rooted at
# the image's /app (FINOPS_REPO_DIR is absent from the container env), so its D-16 repo-alias
# mounts target the /app-in-container paths — which a HOST-view validation refuses ("mount
# target '/app' is outside the four-mount contract"), the w2 refusal shape. The broker now
# validates a request against the view it carries (container-view requests against the
# container-view PathConfig, host-view against the host config) while its OWN launch argv
# always stays the host view.


def test_container_view_request_is_accepted_and_the_w2_refusal_shape_dies(tmp_path):
    """(ws2 VERIFY a) a container-view request — mounts built against a container-view config,
    its D-16 repo-alias targets the /app in-container paths — validates against the container
    view and is ACCEPTED by the broker: the w2 refusal shape dies for the view it carries."""
    host_cfg = _scratch_host_cfg(tmp_path)
    container_cfg = launch_broker.container_view_config(host_cfg)
    assert str(container_cfg.repo_root) == launch_broker.CONTAINER_REPO_ROOT

    request = spawn_wrapper.build_phase_request(
        _PHASE,
        goal="g", workdir="/tmp/wt", model="m", spec_name="spec_x",
        image="fleet/base", path_config=container_cfg,
    )
    # the request's D-16 alias targets are the /app-in-container paths, and it carries the
    # container view (the builder stamps the view of the config it built against).
    alias_targets = {m["target"] for m in request["mounts"]} & {"/app", "/app/.git"}
    assert alias_targets == {"/app", "/app/.git"}
    assert request["view"] == "container"

    # the OLD w2 refusal shape is real: validating this /app request against the HOST view
    # refuses it for the split a container-tier caller cannot see.
    old_errors = spawn_wrapper.validate_spawn({**request, "view": "host"}, path_config=host_cfg)
    assert any("outside" in e for e in old_errors), old_errors

    # the broker validates the request against the view it carries -> ACCEPTED.
    outcome = launch_broker.launch(request, dry_run=True, path_config=host_cfg)
    assert outcome["ok"] is True
    assert launch_broker.validate_launch_request(request, path_config=host_cfg) == []


def test_host_view_request_validates_against_the_host_config(tmp_path):
    """(ws2 VERIFY b) a host-view request validates against the host config — the broker's own
    launch view. A request built against the host config carries the host view and launches
    clean; a legacy request that carries no view at all defaults to host (unchanged behavior)."""
    host_cfg = _scratch_host_cfg(tmp_path)
    request = spawn_wrapper.build_phase_request(
        _PHASE,
        goal="g", workdir="/tmp/wt", model="m", spec_name="spec_x",
        image="fleet/base", path_config=host_cfg,
    )
    assert request["view"] == "host"
    assert launch_broker.launch(request, dry_run=True, path_config=host_cfg)["ok"] is True

    # absent view (a legacy host-side caller) = host view, still accepted.
    del request["view"]
    assert launch_broker.validate_launch_request(request, path_config=host_cfg) == []
    assert launch_broker.launch(request, dry_run=True, path_config=host_cfg)["ok"] is True


def test_an_unknown_view_refuses(tmp_path):
    """(ws2 VERIFY c) a request whose view is neither host nor container refuses — the broker
    validates a request against the view it carries, and an unknown view is one it cannot
    classify. Refused at the typed gate and at the launch path, before any docker argv."""
    host_cfg = _scratch_host_cfg(tmp_path)
    request = spawn_wrapper.build_phase_request(
        _PHASE,
        goal="g", workdir="/tmp/wt", model="m", spec_name="spec_x",
        image="fleet/base", path_config=host_cfg,
    )
    request["view"] = "k8s-cluster"
    errors = launch_broker.validate_launch_request(request, path_config=host_cfg)
    assert any("view" in e and "not one of" in e for e in errors)
    with pytest.raises(launch_broker.LaunchRequestError) as exc:
        launch_broker.launch(request, dry_run=True, path_config=host_cfg)
    assert any("view" in e and "not one of" in e for e in exc.value.errors)


def test_broker_argv_still_uses_the_host_docker_path_for_a_container_view_request(tmp_path):
    """(ws2 VERIFY d) the broker's own launch argv is the HOST view even when it validates a
    container-view request: the /repo source and the D-16 host-path alias bind the HOST repo
    paths — never /app. The container-view mounts are validated, never executed."""
    host_cfg = _scratch_host_cfg(tmp_path)
    container_cfg = launch_broker.container_view_config(host_cfg)
    request = spawn_wrapper.build_phase_request(
        _PHASE,
        goal="g", workdir="/tmp/wt", model="m", spec_name="spec_x",
        image="fleet/base", path_config=container_cfg,
    )
    outcome = launch_broker.launch(request, dry_run=True, path_config=host_cfg)
    joined = " ".join(outcome["argv"])
    assert f"-v {host_cfg.repo_root}:/repo:ro" in joined
    assert f"-v {host_cfg.repo_root}:{host_cfg.repo_root}:ro" in joined  # D-16 host alias
    assert "-v /app:" not in joined
    assert str(container_cfg.git_dir) not in joined


def test_container_view_clone_world_request_validates_and_mounts_the_host_clone(tmp_path):
    """(ws2, the ws1+w2 composition) the clone world too: a container-tier request naming the
    run clone validates against the container view and the broker's argv binds the HOST clone at
    /repo (the executed source is always a host path)."""
    host_cfg = _scratch_host_cfg(tmp_path)
    container_cfg = launch_broker.container_view_config(host_cfg)
    clone = host_cfg.runs_root / "run-abc" / "repo"
    request = spawn_wrapper.build_phase_request(
        _PHASE,
        goal="g", workdir="/tmp/wt", model="m", spec_name="spec_x",
        image="fleet/base", path_config=container_cfg, run_clone=str(clone),
    )
    assert request["view"] == "container"
    outcome = launch_broker.launch(request, dry_run=True, path_config=host_cfg)
    assert outcome["ok"] is True
    assert f"-v {clone}:/repo:rw" in " ".join(outcome["argv"])


def test_existing_refusals_are_unchanged_with_the_view_field():
    """(ws2 VERIFY e) the existing validation refusals are unchanged for a request that carries
    its view — a bad mount profile and an untyped/shell command still refuse at the typed gate
    and at the launch path, exactly as before the view field existed."""
    bad_profile = _built_request(mount_profile="hypervisor_root")
    assert any("not one of the fixed profiles" in e
               for e in launch_broker.validate_launch_request(bad_profile))
    shell_command = _built_request(command="docker run ubuntu bash")
    assert any("command must be a non-empty list" in e
               for e in launch_broker.validate_launch_request(shell_command))
    for bad in (bad_profile, shell_command):
        with pytest.raises(launch_broker.LaunchRequestError):
            launch_broker.launch(bad, dry_run=True)


# ── (f) the shared validation keeps the same refusals ────────────────────────


def test_broker_re_runs_the_wrappers_scope_model_and_keeps_the_same_refusal():
    """The broker validates what it will execute with the SAME checks the wrapper ran.

    F3 (fleet_launch_container_smoke cs4) refined the boundary: phase AUTHORIZATION is the
    wrapper's gate (it alone has the spec's declared scopes — a custom spec's phases
    legitimately declare their scope, which the static table cannot know); the broker
    re-validates the LAUNCH MECHANICS (vocabulary membership, mount contract, lease, view)
    against the request's own resolved scope. A scope OUTSIDE the closed vocabulary still
    refuses at the broker (step 1) before any docker argv is built; a wrapper-validated
    declared scope passes the broker's mechanics checks."""
    request = _built_request(phase="p6_adversarial", scope="not-a-scope")
    with pytest.raises(launch_broker.LaunchRequestError) as exc:
        launch_broker.launch(request, dry_run=True)
    assert any("step 1" in e and "vocabulary" in e for e in exc.value.errors)


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
    # fb2_broker_hostside: the wrapper's docker-touching entry points delegate to the host
    # broker OVER THE SEAM — the in-process broker import is gone (the wrapper no longer
    # imports launch_broker or calls launch_broker.launch/submit_run/run_fleet_command; it
    # speaks the unix-socket seam through broker_client).
    assert "import launch_broker" not in src
    assert "launch_broker." not in src
    assert "from broker_client import BrokerClient" in src
    # the call sites are the seam client's typed verbs (assert the call site, fb2 VERIFY b).
    assert "_broker_client().launch(" in src
    assert "_broker_client().submit(" in src
    assert "_broker_client().fleet_command(" in src
    # no argv builders in the wrapper (they live in the broker module).
    assert "def build_spawn_argv" not in src
    assert "def build_submit_argv" not in src
    assert "def build_launch_argv" not in src


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


# ── the deployment probe (remediation closed-loop, decision f987cde9) ─────────


def _git_repo_with_main(tmp_path: Path, name: str) -> Path:
    """A real git repo with a ``main`` branch and one commit — the probe's judged state."""
    import subprocess

    repo = tmp_path / name
    repo.mkdir(parents=True)
    subprocess.run(["git", "-C", str(repo), "init", "-q", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    (repo / "f.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "f.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "c1"], check=True)
    return repo


def _add_commit(repo: Path, text: str) -> None:
    import subprocess

    (repo / "f.txt").write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "f.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", text[:40]], check=True)


def test_deployment_probe_is_silent_when_unjudgeable(tmp_path):
    """Neither side a git tree → no fabricated refusal (the clone path names those)."""
    repo = _git_repo_with_main(tmp_path, "repo")
    assert launch_broker.deployment_probe(str(tmp_path / "no_such_workdir"), repo_root=repo) == []
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    assert launch_broker.deployment_probe(str(not_a_repo), repo_root=tmp_path / "no_repo") == []


def test_deployment_probe_allows_workdir_at_main(tmp_path):
    """A worktree exactly at the repo's main tip is the legal base."""
    import subprocess

    repo = _git_repo_with_main(tmp_path, "repo")
    wd = tmp_path / "wt_at"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(wd), "main"], check=True)
    assert launch_broker.deployment_probe(str(wd), repo_root=repo) == []


def test_deployment_probe_allows_workdir_ahead_of_main(tmp_path):
    """A resume worktree (phase commits ahead of main) is legal — main is its ancestor."""
    import subprocess

    repo = _git_repo_with_main(tmp_path, "repo")
    wd = tmp_path / "wt_ahead"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(wd), "main"], check=True)
    _add_commit(wd, "resume commit ahead of main")
    assert launch_broker.deployment_probe(str(wd), repo_root=repo) == []


def test_deployment_probe_refuses_stale_workdir(tmp_path):
    """The 2026-09-13 failure class: workdir behind main silently minted dead-tree clones."""
    import subprocess

    repo = _git_repo_with_main(tmp_path, "repo")
    wd = tmp_path / "wt_stale"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(wd), "main"], check=True)
    _add_commit(repo, "main moved on")
    errors = launch_broker.deployment_probe(str(wd), repo_root=repo)
    assert len(errors) == 1
    assert "workdir base" in errors[0] and "reset --hard origin/main" in errors[0]


def test_deployment_probe_refuses_diverged_workdir(tmp_path):
    """A worktree on its own lineage is refused the same way — never a stale clone."""
    import subprocess

    repo = _git_repo_with_main(tmp_path, "repo")
    wd = tmp_path / "wt_diverged"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(wd), "main"], check=True)
    _add_commit(wd, "other lineage commit")
    _add_commit(repo, "main moved on while other stayed")
    errors = launch_broker.deployment_probe(str(wd), repo_root=repo)
    assert len(errors) == 1 and "workdir base" in errors[0]


def test_submit_run_fires_the_probe_before_any_compose_call(tmp_path):
    """The broker path refuses a stale-workdir submit at the last gate — no compose argv."""
    import shutil
    import subprocess

    repo = _git_repo_with_main(tmp_path, "repo")
    spec_dir = repo / "workflows" / "repository"
    spec_dir.mkdir(parents=True)
    shutil.copy(_REPO_ROOT / "workflows" / "repository" / "control_room_facelift_review.yaml",
                spec_dir / "control_room_facelift_review.yaml")
    wd = tmp_path / "wt_stale"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(wd), "main"], check=True)
    _add_commit(repo, "main moved on")
    command = {
        "spec": "workflows/repository/control_room_facelift_review.yaml",
        "goal": "g", "model": "deepseek/deepseek-v4-flash", "workdir": str(wd),
    }
    with pytest.raises(launch_broker.LaunchRequestError) as exc:
        launch_broker.submit_run(command, repo_root=repo, compose="docker-compose", dry_run=True)
    assert any("workdir base" in e for e in exc.value.errors)


# ── The extended submit contract (AIO remediation 2026-09-14) ────────────────
#
# Source/spec identity, continuation identity, and applicable admission settings must
# survive every hop of the durable submit path — and the last gate must refuse a submit
# that would arrive disarmed or with a wrong digest.


def test_build_submit_argv_carries_the_extended_identity():
    """The compose argv carries resume/parent-run/admission — nothing is dropped at the hop."""
    argv = launch_broker.build_submit_argv({
        "job_id": "abc123",
        "spec": "workflows/repository/x.yaml",
        "goal": "g",
        "model": "deepseek/deepseek-v4-flash",
        "workdir": "/tmp/wt_x",
        "resume": True,
        "parent_run_id": "run-1",
        "admission": {"required": True, "campaign_budget_usd": 20.0, "campaign_concurrency": 4},
    }, compose="dc", compose_file="/c.yml")
    assert "-e" in argv and "FINOPS_CELL_ID=abc123" in argv
    assert "FINOPS_ADMISSION_REQUIRED=1" in argv, "the armed gate must cross the compose boundary"
    assert "--resume" in argv and "--parent-run-id" in argv and "run-1" in argv
    assert "--campaign-budget-usd" in argv and "20.0" in argv
    assert "--campaign-concurrency" in argv and "4" in argv


def test_build_submit_argv_without_admission_does_not_arm():
    """A submit that declares no admission settings produces NO admission env — the run's
    own composition root prints its disarmed state, but the submit never fabricates arming."""
    argv = launch_broker.build_submit_argv({
        "spec": "workflows/repository/x.yaml", "goal": "g",
        "model": "deepseek/deepseek-v4-flash", "workdir": "/tmp/wt_x",
    }, compose="dc", compose_file="/c.yml")
    assert "FINOPS_ADMISSION_REQUIRED=1" not in argv


def test_deployment_probe_verifies_the_declared_spec_digest(tmp_path):
    """The declared immutable input is verified against the repo's bytes: a mismatch refuses,
    a match passes (and the stale-workdir rule still applies after it)."""
    import subprocess

    repo = _git_repo_with_main(tmp_path, "repo")
    spec_dir = repo / "workflows" / "repository"
    spec_dir.mkdir(parents=True)
    spec_path = spec_dir / "s.yaml"
    spec_path.write_text("name: s\n")
    wd = tmp_path / "wt"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(wd), "main"], check=True)

    import hashlib
    good = hashlib.sha256(spec_path.read_bytes()).hexdigest()
    assert launch_broker.deployment_probe(
        str(wd), repo_root=repo, spec_rel="workflows/repository/s.yaml", spec_sha256=good
    ) == []
    errors = launch_broker.deployment_probe(
        str(wd), repo_root=repo, spec_rel="workflows/repository/s.yaml", spec_sha256="0" * 64
    )
    assert any("digest mismatch" in e for e in errors)


def test_deployment_probe_resume_skips_the_main_freshness_refusal(tmp_path):
    """A declared resume is never destroyed by unrelated main advances: the pinned continuation
    skips the stale-workdir refusal (its lineage is the parent-run linkage, checked by the
    run's own composition root against the control db)."""
    import subprocess

    repo = _git_repo_with_main(tmp_path, "repo")
    wd = tmp_path / "wt_resume"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(wd), "main"], check=True)
    _add_commit(wd, "[workflow] p0a_reanchor_parity — resume work ahead of main")
    _add_commit(repo, "main moved on after the run started")
    # fresh submit: refused (stale)
    assert launch_broker.deployment_probe(str(wd), repo_root=repo) != []
    # the SAME workdir as a resume: the declared continuation is legitimate
    assert launch_broker.deployment_probe(str(wd), repo_root=repo, resume=True) == []


def test_submit_run_refuses_an_unarmed_command_when_the_host_gate_is_armed(tmp_path, monkeypatch):
    """The disarmed-submit refusal: admission armed on the host + a command with no admission
    settings = REFUSED before any compose call (a successful 'gate disarmed' launch is the
    failure this contract removes)."""
    import shutil
    import subprocess

    repo = _git_repo_with_main(tmp_path, "repo")
    spec_dir = repo / "workflows" / "repository"
    spec_dir.mkdir(parents=True)
    shutil.copy(_REPO_ROOT / "workflows" / "repository" / "control_room_facelift_review.yaml",
                spec_dir / "control_room_facelift_review.yaml")
    wd = tmp_path / "wt"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(wd), "main"], check=True)
    command = {
        "spec": "workflows/repository/control_room_facelift_review.yaml",
        "goal": "g", "model": "deepseek/deepseek-v4-flash", "workdir": str(wd),
    }
    monkeypatch.setenv("FINOPS_ADMISSION_REQUIRED", "1")
    with pytest.raises(launch_broker.LaunchRequestError) as exc:
        launch_broker.submit_run(command, repo_root=repo, compose="dc", dry_run=True)
    assert any("never silently disarms" in e for e in exc.value.errors)
    # the armed command passes the same gate
    command["admission"] = {"required": True}
    outcome = launch_broker.submit_run(command, repo_root=repo, compose="dc", dry_run=True)
    assert outcome.get("ok") is True
    assert "FINOPS_ADMISSION_REQUIRED=1" in outcome["argv"]


def test_build_submit_argv_carries_the_execution_settings():
    """Astra finding: every accepted execution setting must survive the hop — the run the
    caller requested IS the run that executes."""
    argv = launch_broker.build_submit_argv({
        "spec": "workflows/repository/x.yaml", "goal": "g",
        "model": "deepseek/deepseek-v4-flash", "workdir": "/tmp/wt_x",
        "execution": {
            "backend": "claude_cli", "thinking_effort": "high",
            "thinking_budget_tokens": 12000, "output_token_limit": 64000,
            "timeout_seconds": 2400, "no_commit": True,
        },
    }, compose="dc", compose_file="/c.yml")
    assert "--backend" in argv and "claude_cli" in argv
    assert "--thinking-effort" in argv and "high" in argv
    assert "--thinking-budget-tokens" in argv and "12000" in argv
    assert "--output-token-limit" in argv and "64000" in argv
    assert "--timeout" in argv and "2400" in argv
    assert "--no-commit" in argv


def test_build_submit_argv_carries_the_reserve_and_cap():
    """The armed gate's per-token leases DENY without a stated reserve (2026-09-14: the armed
    resubmission died with `cost_source=unknown`). The reserve/cap values must survive the hop
    exactly like the other admission settings."""
    argv = launch_broker.build_submit_argv({
        "spec": "workflows/repository/x.yaml", "goal": "g",
        "model": "deepseek/deepseek-v4-flash", "workdir": "/tmp/wt_x",
        "admission": {"required": True, "campaign_budget_usd": 20.0,
                      "reserve_usd": 0.6, "hard_cap_usd": 1.0},
    }, compose="dc", compose_file="/c.yml")
    assert "FINOPS_RESERVE_USD=0.6" in argv
    assert "FINOPS_HARD_CAP_USD=1.0" in argv
    # absent fields stay absent — never a fabricated zero
    bare = launch_broker.build_submit_argv({
        "spec": "workflows/repository/x.yaml", "goal": "g",
        "model": "deepseek/deepseek-v4-flash", "workdir": "/tmp/wt_x",
    }, compose="dc", compose_file="/c.yml")
    assert not any("FINOPS_RESERVE_USD" in a for a in bare)
    assert not any("FINOPS_HARD_CAP_USD" in a for a in bare)


def test_every_env_flag_precedes_the_service_name():
    """`docker compose run` takes options BEFORE the service; everything after it is the
    container command. The first reserve fix (2026-09-14) appended `-e FINOPS_RESERVE_USD=…`
    after ``run_workflow.py`` and compose handed it to the script ("unrecognized arguments").
    Membership alone missed it — THIS asserts position for every `-e` the builder emits."""
    argv = launch_broker.build_submit_argv({
        "job_id": "abc123",
        "spec": "workflows/repository/x.yaml", "goal": "g",
        "model": "deepseek/deepseek-v4-flash", "workdir": "/tmp/wt_x",
        "resume": True, "parent_run_id": "run-1",
        "execution": {"no_commit": True, "timeout_seconds": 60},
        "admission": {"required": True, "campaign_budget_usd": 20.0,
                      "campaign_concurrency": 1, "reserve_usd": 0.6, "hard_cap_usd": 1.0},
    }, compose="dc", compose_file="/c.yml")
    service_at = argv.index("workflow-runner")
    env_positions = [i for i, token in enumerate(argv) if token == "-e"]
    assert env_positions, "no env flags emitted"
    for pos in env_positions:
        assert pos < service_at, f"'-e' at {pos} lands after the service name ({service_at})"
        value = argv[pos + 1]
        assert "=" in value and not value.startswith("-"), value
    # and no stray env-looking token is passed as a container command argument
    command_part = argv[service_at + 1:]
    assert not any(token.startswith("FINOPS_") for token in command_part)


# ── The AIO binding gate at the broker (Unit D) ───────────────────────────────
#
# The broker re-validates every submit with the shared gate BEFORE the launch effect: an
# unbound AIO submission never reaches the compose call, even when it bypasses the wrapper.
# A bound submission proceeds exactly as before.


def _aio_command(**overrides) -> dict:
    command = {
        "spec": "workflows/repository/fleet_job_submission.yaml",
        "goal": "g",
        "model": "anthropic/claude-sonnet-5",
        "workdir": "/tmp/wt_aio_broker_check",
        "actor": "aio",
        "aio": {
            "native_session_id": "ses_aio",
            "agent": "aio-control",
            "binding_id": "0" * 64,
            "task_revision": 1,
        },
    }
    command.update(overrides)
    return command


def _healthy_opencode_db(path, monkeypatch) -> None:
    """A canonical session db whose ACTIVE model resolves capacity (hermetic catalog)."""
    import json as _json
    import sqlite3

    catalog = path.parent / "models.json"
    catalog.write_text(_json.dumps({
        "deepseek": {"models": {"deepseek-v4-flash": {"limit": {"context": 1_000_000, "output": 384_000}}}}
    }), encoding="utf-8")
    monkeypatch.setenv("FINOPS_OPENCODE_MODELS_CACHE", str(catalog))
    monkeypatch.setenv("FINOPS_SESSION_CAPACITY_SOURCE", "catalog")
    (path.parent / "config-home").mkdir(exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(path.parent / "config-home"))
    con = sqlite3.connect(path)
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


def test_an_unbound_aio_submit_is_refused_with_zero_launch_calls(tmp_path, monkeypatch):
    """The REQUIRED regression (Unit D): bypass the wrapper, submit directly to the backend
    with an AIO identity and no resolvable binding — the launch effect must never run."""
    monkeypatch.setattr(launch_broker, "admission_required", lambda: False)
    monkeypatch.setenv("FINOPS_KB_ARTIFACT_DIR", str(tmp_path / "absent"))
    calls: list = []

    def _forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError("the launch effect ran for an unbound AIO submit")

    monkeypatch.setattr(launch_broker.subprocess, "run", _forbidden)
    with pytest.raises(launch_broker.LaunchRequestError) as exc:
        launch_broker.submit_run(
            _aio_command(), repo_root=launch_broker._REPO_ROOT, compose="docker-compose"
        )
    assert any("binding" in e for e in exc.value.errors)
    assert calls == []


def test_a_bound_aio_submit_still_reaches_the_compose_call(tmp_path, monkeypatch):
    """The bound counterpart: normal submission still works, through the same gate."""
    from agentic_dynamics.knowledge import session_ingestion as si

    store = tmp_path / "kb"
    si.init_binding_store(store)
    written = si.write_binding(
        {
            "native_session_id": "ses_aio",
            "resolved_agent": "aio-control",
            "task_identity": "unit-d",
            "original_request": "enforce the binding at the exec boundary",
        },
        artifact_dir=store,
        publish=False,
    )
    assert written.status == si.BINDING_STATUS_CREATED
    monkeypatch.setenv("FINOPS_KB_ARTIFACT_DIR", str(store))
    _healthy_opencode_db(tmp_path / "opencode.db", monkeypatch)
    monkeypatch.setenv("FINOPS_OPENCODE_DB", str(tmp_path / "opencode.db"))
    monkeypatch.setattr(launch_broker, "admission_required", lambda: False)
    # The deployment probe is a DIFFERENT gate (its own tests cover it) — stub it to isolate.
    monkeypatch.setattr(launch_broker, "deployment_probe", lambda *a, **k: [])
    calls: list = []

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(
        launch_broker.subprocess, "run", lambda argv, **kw: calls.append(argv) or _Proc()
    )
    command = _aio_command(
        aio={
            "native_session_id": "ses_aio",
            "agent": "aio-control",
            "binding_id": si.binding_authorization_id(
                si.read_binding("ses_aio", artifact_dir=store).binding or {}
            ),
            "task_revision": 1,
        }
    )
    outcome = launch_broker.submit_run(
        command, repo_root=launch_broker._REPO_ROOT, compose="docker-compose"
    )
    assert outcome["ok"] is True
    assert len(calls) == 1
    assert "workflow-runner" in " ".join(calls[0])


# ── The actor declaration at the broker (reviewer repair) ─────────────────────


def test_actor_aio_without_a_block_never_reaches_the_launch_effect(monkeypatch):
    monkeypatch.setattr(launch_broker, "admission_required", lambda: False)
    calls: list = []

    def _forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError("the launch effect ran for an inconsistent AIO declaration")

    monkeypatch.setattr(launch_broker.subprocess, "run", _forbidden)
    for command in (
        {**_aio_command(), "aio": None},
        {key: value for key, value in _aio_command().items() if key != "aio"},
    ):
        with pytest.raises(launch_broker.LaunchRequestError) as exc:
            launch_broker.submit_run(command, repo_root=launch_broker._REPO_ROOT, compose="dc")
        assert any("binding block" in e for e in exc.value.errors)
    assert calls == []


def test_the_complete_submission_path_host_shape(tmp_path, monkeypatch):
    """The production arrangement, host side: the manager's envelope → the broker's strict
    gate (REAL budget measurement against the canonical-shaped DB) → ONE compose call."""
    import importlib
    import sys

    from agentic_dynamics.knowledge import session_ingestion as si

    fleet_dir = str(launch_broker._REPO_ROOT / "scripts" / "fleet")
    if fleet_dir not in sys.path:
        sys.path.insert(0, fleet_dir)
    fleet_manager = importlib.import_module("fleet_manager")

    class _FakeRedis:
        def __init__(self):
            self._lists: dict[str, list[str]] = {}

        def lpush(self, key, value):
            self._lists.setdefault(key, []).insert(0, value)

        def hset(self, key, mapping=None, **_kw):
            pass

        def hvals(self, key):
            return []

    store = tmp_path / "kb"
    si.init_binding_store(store)
    si.write_binding(
        {
            "native_session_id": "ses_aio",
            "resolved_agent": "aio-control",
            "task_identity": "unit-d",
            "original_request": "walk the complete submission path",
        },
        artifact_dir=store,
        publish=False,
    )
    monkeypatch.setenv("FINOPS_KB_ARTIFACT_DIR", str(store))
    _healthy_opencode_db(tmp_path / "opencode.db", monkeypatch)
    monkeypatch.setenv("FINOPS_OPENCODE_DB", str(tmp_path / "opencode.db"))
    monkeypatch.setattr(launch_broker, "admission_required", lambda: False)
    monkeypatch.setattr(launch_broker, "deployment_probe", lambda *a, **k: [])

    # 1) the manager mints the job envelope with the AIO identity, exactly as the tool
    #    stamps it (the block + the actor travel together).
    queued = fleet_manager._send_submit_command(
        _FakeRedis(),
        spec="workflows/repository/fleet_job_submission.yaml",
        goal="g",
        model="anthropic/claude-sonnet-5",
        workdir="/tmp/wt_complete_path",
        aio={
            "native_session_id": "ses_aio",
            "agent": "aio-control",
            "binding_id": si.binding_authorization_id(
                si.read_binding("ses_aio", artifact_dir=store).binding or {}
            ),
            "task_revision": 1,
        },
    )
    assert queued["actor"] == "aio"

    calls: list = []

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(
        launch_broker.subprocess, "run", lambda argv, **kw: calls.append(argv) or _Proc()
    )
    outcome = launch_broker.submit_run(
        queued, repo_root=launch_broker._REPO_ROOT, compose="docker-compose"
    )
    assert outcome["ok"] is True
    assert len(calls) == 1 and "workflow-runner" in " ".join(calls[0])
