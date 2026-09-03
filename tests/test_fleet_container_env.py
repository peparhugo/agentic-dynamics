"""cs1_container_env — the container tier carries the repo view (fleet_launch_container_smoke).

fleet_launch_smoke's adversarial review F1: the container env (``x-ladder-env`` /
``x-orchestrator-base``) never carried ``FINOPS_REPO_DIR``/``FINOPS_GIT_DIR``, so a
container-tier orchestrator derived its repo view implicitly (``PROJECT_ROOT``), which
(a) left the ws2 view discriminator keyed to a path the compose topology never produces and
(b) made the clone-world shared-surface check mis-flag a container cell's OWN ``/repo`` clone
mount (``repo_root == /repo == REPO_TARGET``) — refusing every containerized clone spawn.
cs1 sets the env in the container tier so the container derives the SAME repo view the broker
validates. These unit tests prove both directions of the cs1 VERIFY:

(a) docker-compose.ladder.yml's container env (``x-ladder-env``) AND the orchestrator-tier env
    (``x-orchestrator-base`` → ``campaign-wrapper`` / ``workflow-runner``) carry
    ``FINOPS_REPO_DIR`` / ``FINOPS_GIT_DIR`` set to the container-visible repo path ``/repo`` +
    ``/repo/.git`` (parse the yml, assert the keys) — no tier derives its view differently;

(b) a container-view path derivation WITH those env vars (``PathConfig.from_env`` on the
    compose's own env block) produces the broker-expected view: the ws2 discriminator keys a
    ``/repo``-rooted config into the SAME (host) view family the broker validates its spawn
    requests against — and a clone-world request built from that config (the fleet's real
    shape) is ACCEPTED end to end (client-side validate + broker dry-run launch binds the host
    clone at ``/repo``), where the f1(b) shared-surface collision used to refuse it.

Pure-unit: no docker, no subprocess, no git worktrees — only the compose YAML, the pure
validators, and the broker's dry-run launch path.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from agentic_dynamics.core.paths import PathConfig

ROOT = Path(__file__).resolve().parent.parent
COMPOSE_PATH = ROOT / "infrastructure" / "docker-compose.ladder.yml"

_FLEET_DIR = str(ROOT / "scripts" / "fleet")
if _FLEET_DIR not in sys.path:
    sys.path.insert(0, _FLEET_DIR)

from scripts.fleet import launch_broker, spawn_wrapper  # noqa: E402

#: The cs1 env values — the container-visible repo path (the /repo mount + its .git). Kept next
#: to the yml assertion so the test can never pass a value the yml does not carry.
REPO_DIR = "/repo"
GIT_DIR = "/repo/.git"

#: cs3_container_smoke — the shared RUNS root. A container orchestrator mints its per-run clone
#: at this path (create_run_clone → runs_root/<run-id>/repo), so it must be the SHARED /tmp path
#: the HOST broker validates and bind-mounts into the cell — never the container-local
#: /var/lib/agentic-dynamics/runs default (a different namespace; the real-shape smoke proved a
#: container orchestrator cannot spawn without the override in play). The compose env carries the
#: operator's host override when exported, else this /tmp default.
RUNS_ROOT = "/tmp/agentic-dynamics-runs"
RUNS_ROOT_ENV = "FINOPS_RUNS_ROOT"

_PHASE = {"name": "p1_slice1_base_supervisor", "scope": "implementation"}


def _compose() -> dict:
    """Parse docker-compose.ladder.yml once (yaml.safe_load resolves the ``<<`` merge keys, so a
    service's ``environment`` already includes the anchors it merges)."""
    return yaml.safe_load(COMPOSE_PATH.read_text())


# ── (a) the compose env carries FINOPS_REPO_DIR / FINOPS_GIT_DIR for the orchestrator tier ──


def test_x_ladder_env_carries_the_repo_view():
    """(cs1 VERIFY a) ``x-ladder-env`` — the canonical container env anchor merged into every
    tier — carries ``FINOPS_REPO_DIR``/``FINOPS_GIT_DIR`` set to the container-visible repo path
    (``/repo`` + ``/repo/.git``), as LITERAL container env values (never a host-side
    ``${FINOPS_REPO_DIR}`` mount-source interpolation)."""
    env = _compose()["x-ladder-env"]
    assert env.get("FINOPS_REPO_DIR") == REPO_DIR, (
        f"x-ladder-env must set FINOPS_REPO_DIR to the container-visible {REPO_DIR!r}, got "
        f"{env.get('FINOPS_REPO_DIR')!r}"
    )
    assert env.get("FINOPS_GIT_DIR") == GIT_DIR, (
        f"x-ladder-env must set FINOPS_GIT_DIR to {GIT_DIR!r}, got {env.get('FINOPS_GIT_DIR')!r}"
    )
    # a container env value is a literal path, never an unresolved interpolation
    for key in ("FINOPS_REPO_DIR", "FINOPS_GIT_DIR"):
        assert "${" not in str(env[key]), (
            f"{key} leaked a host interpolation into the container env"
        )


def test_orchestrator_tier_env_carries_the_repo_view():
    """(cs1 VERIFY a) the orchestrator tier carries the repo view EXPLICITLY: the
    ``x-orchestrator-base`` anchor AND both orchestrator services (``campaign-wrapper`` and
    ``workflow-runner`` — the reference containerized execution path) declare
    ``FINOPS_REPO_DIR``/``FINOPS_GIT_DIR`` at the container-visible repo path."""
    compose = _compose()
    anchor_env = compose["x-orchestrator-base"]["environment"]
    assert anchor_env.get("FINOPS_REPO_DIR") == REPO_DIR
    assert anchor_env.get("FINOPS_GIT_DIR") == GIT_DIR
    for service in ("campaign-wrapper", "workflow-runner"):
        env = compose["services"][service]["environment"]
        assert env.get("FINOPS_REPO_DIR") == REPO_DIR, (
            f"{service} must carry FINOPS_REPO_DIR={REPO_DIR!r} (got {env.get('FINOPS_REPO_DIR')!r})"
        )
        assert env.get("FINOPS_GIT_DIR") == GIT_DIR, (
            f"{service} must carry FINOPS_GIT_DIR={GIT_DIR!r} (got {env.get('FINOPS_GIT_DIR')!r})"
        )


def test_every_tier_derives_the_same_repo_view():
    """(hard rule 3 — no tier derives its view differently) the repo view vars ride in
    ``x-ladder-env``, which every tier anchor merges: the cell tier (``x-cell-base``), the
    supervisor tier (``x-supervisor-base``) and the orchestrator tier (``x-orchestrator-base``)
    all carry the same container-visible ``/repo`` + ``/repo/.git``."""
    compose = _compose()
    for anchor in ("x-cell-base", "x-supervisor-base", "x-orchestrator-base"):
        env = compose[anchor]["environment"]
        assert env.get("FINOPS_REPO_DIR") == REPO_DIR, (
            f"{anchor} env: {env.get('FINOPS_REPO_DIR')!r}"
        )
        assert env.get("FINOPS_GIT_DIR") == GIT_DIR, f"{anchor} env: {env.get('FINOPS_GIT_DIR')!r}"


# ── (cs3) the container tier carries the shared RUNS root (the real-shape smoke's fix) ─────────


def _runs_root_default(raw: str) -> str:
    """The concrete default behind a compose ``${FINOPS_RUNS_ROOT:-<default>}`` interpolation."""
    return raw.split(":-", 1)[1].rstrip("}") if ":-" in raw else raw


def test_x_ladder_env_carries_the_shared_runs_root():
    """(cs3 VERIFY) ``x-ladder-env`` — merged into every tier — carries ``FINOPS_RUNS_ROOT`` whose
    value is the SHARED /tmp runs root (an interpolation whose fallback is the ws4-era
    ``/tmp/agentic-dynamics-runs`` override), never the container-local ``/var/lib/...`` default a
    container orchestrator would otherwise derive."""
    env = _compose()["x-ladder-env"]
    raw = env.get(RUNS_ROOT_ENV)
    assert raw is not None, "x-ladder-env must carry FINOPS_RUNS_ROOT"
    assert ":-" in str(raw), "FINOPS_RUNS_ROOT must interpolate the host override with a fallback"
    default = _runs_root_default(str(raw))
    assert default == RUNS_ROOT, (
        f"x-ladder-env FINOPS_RUNS_ROOT fallback must be the shared {RUNS_ROOT!r}, got {default!r}"
    )
    assert "/var/lib/agentic-dynamics" not in str(raw), (
        "the container tier must not fall back to the container-local /var/lib runs root"
    )


def test_orchestrator_tier_env_carries_the_shared_runs_root():
    """(cs3 VERIFY) the orchestrator tier carries the runs root EXPLICITLY — ``x-orchestrator-base``
    AND both orchestrator services (``campaign-wrapper`` / ``workflow-runner``) declare
    ``FINOPS_RUNS_ROOT`` with the same shared-/tmp fallback, so a container orchestrator's
    create_run_clone lands where the host broker validates."""
    compose = _compose()
    for label, env in [("x-orchestrator-base", compose["x-orchestrator-base"]["environment"])] + [
        (s, compose["services"][s]["environment"]) for s in ("campaign-wrapper", "workflow-runner")
    ]:
        raw = env.get(RUNS_ROOT_ENV)
        assert raw is not None, f"{label} must carry FINOPS_RUNS_ROOT"
        assert _runs_root_default(str(raw)) == RUNS_ROOT, (
            f"{label} FINOPS_RUNS_ROOT fallback must be {RUNS_ROOT!r}"
        )


def test_every_tier_carries_the_same_runs_root():
    """(hard rule 3) the runs root rides in ``x-ladder-env``, so the cell, supervisor and
    orchestrator tier anchors all carry the same shared-/tmp ``FINOPS_RUNS_ROOT`` fallback."""
    compose = _compose()
    for anchor in ("x-cell-base", "x-supervisor-base", "x-orchestrator-base"):
        raw = compose[anchor]["environment"].get(RUNS_ROOT_ENV)
        assert raw is not None, f"{anchor} env must carry FINOPS_RUNS_ROOT"
        assert _runs_root_default(str(raw)) == RUNS_ROOT, f"{anchor} runs-root fallback"


def test_container_view_derivation_uses_the_shared_runs_root(tmp_path):
    """(cs3 VERIFY) deriving the path config from the cs1+c3 container env yields the SHARED runs
    root (``runs_root=/tmp/agentic-dynamics-runs``) — not the container-local
    ``/var/lib/agentic-dynamics/runs`` default — so create_run_clone writes a host-broker-visible
    clone path (``/tmp/agentic-dynamics-runs/<run-id>/repo``), exactly what the broker's
    ``is_run_clone_dir`` accepts and bind-mounts."""
    env = _container_env(tmp_path)
    env[RUNS_ROOT_ENV] = RUNS_ROOT
    cfg = PathConfig.from_env(env, require_existing=False)
    assert str(cfg.runs_root) == RUNS_ROOT
    clone = cfg.runs_root / "run-abc" / "repo"
    assert cfg.is_run_clone_dir(clone) is True


# ── (b) a container-view path derivation with those env vars → broker-expected view ─────────


def _container_env(tmp_path) -> dict[str, str]:
    """The env a container-tier orchestrator boots with after cs1: the compose ``x-ladder-env``
    repo-view vars + the shared-scope paths both sides of the seam agree on (the worktree root,
    the shared runs root, the state root and the auth home — hermetic scratch values here)."""
    return {
        "FINOPS_REPO_DIR": REPO_DIR,
        "FINOPS_GIT_DIR": GIT_DIR,
        "FINOPS_WORKTREE_ROOT": "/tmp",
        "FINOPS_RUNS_ROOT": str(tmp_path / "runs"),
        "FINOPS_OPENCODE_STATE_ROOT": str(tmp_path / "state"),
        "AUTH_HOME": str(tmp_path / "auth"),
        "HOME": str(tmp_path / "auth"),
    }


def _scratch_host_cfg(tmp_path):
    """The broker's HOST-view config (a scratch repo under ``tmp_path``), the same hermetic
    shape as the wrapper/broker suites' ``_scratch_host_cfg``."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "experiments" / "results").mkdir(parents=True)
    auth = tmp_path / "auth"
    (auth / ".local" / "share" / "opencode").mkdir(parents=True)
    return PathConfig(
        repo_root=repo,
        git_dir=repo / ".git",
        worktrees_root=tmp_path / "worktrees",
        runs_root=tmp_path / "runs",
        results_dir=repo / "experiments" / "results",
        state_root=tmp_path / "state",
        auth_home=auth,
    )


def test_container_view_derivation_roots_at_the_repo_mount(tmp_path):
    """(cs1 VERIFY b) deriving the path config from the cs1 container env yields the
    container-visible repo view: ``repo_root=/repo``, ``git_dir=/repo/.git`` and
    ``results_dir=/repo/experiments/results`` (the compose ``working_dir`` / repo mount / results
    overlay) — never the image's stale baked ``/app`` copy, never the host checkout path."""
    cfg = PathConfig.from_env(_container_env(tmp_path), require_existing=False)
    assert cfg.repo_root == Path(REPO_DIR)
    assert cfg.git_dir == Path(GIT_DIR)
    assert cfg.results_dir == Path(REPO_DIR) / "experiments" / "results"


def test_the_ws2_discriminator_keys_the_cs1_config_to_the_broker_validated_view(tmp_path):
    """(cs1 VERIFY b) the ws2 discriminator keys a config derived from the cs1 container env to
    the SAME view the broker validates its spawn requests against. The container tier now
    carries the repo view explicitly (repo_root=/repo — the compose /repo mount), so its config
    is classified in the host family (the unified repo-view family, never the legacy baked-image
    /app container view): a request built from it is validated + launched as the broker's own
    view configs are, and the D-16 repo-alias split that ws2's /app keying existed to paper over
    is gone."""
    host_cfg = _scratch_host_cfg(tmp_path)
    container_cfg = PathConfig.from_env(_container_env(tmp_path), require_existing=False)

    assert spawn_wrapper.config_view(container_cfg) == launch_broker.VIEW_HOST
    assert spawn_wrapper.config_view(container_cfg) != launch_broker.VIEW_CONTAINER
    # the discriminator still distinguishes the LEGACY baked-image view (/app) — the ws2
    # container-view machinery stays intact for configs that root at the image's /app copy.
    legacy = launch_broker.container_view_config(host_cfg)
    assert spawn_wrapper.config_view(legacy) == launch_broker.VIEW_CONTAINER

    request = spawn_wrapper.build_phase_request(
        _PHASE,
        goal="g",
        workdir="/tmp/wt",
        model="m",
        spec_name="spec_x",
        image="fleet/base",
        path_config=container_cfg,
    )
    assert request["view"] == launch_broker.VIEW_HOST
    # accepted through the broker's launch path (dry-run) against the host config.
    assert launch_broker.validate_launch_request(request, path_config=host_cfg) == []
    assert launch_broker.launch(request, dry_run=True, path_config=host_cfg)["ok"] is True


def test_clone_world_request_from_the_cs1_config_is_accepted_not_refused(tmp_path):
    """(cs1 VERIFY b — the f1(b) shape) a CLONE-world request built from the cs1-env container
    config (repo_root=/repo — the fleet's real spawn shape) is ACCEPTED end to end: the
    client-side scope validation no longer mis-flags the cell's OWN /repo clone mount as the
    shared worktree/.git surface, and the broker's dry-run launch binds the HOST clone at /repo.
    Before cs1, ``repo_root == /repo == REPO_TARGET`` tripped the shared-surface collision and
    every containerized clone spawn was refused before the broker was reached."""
    host_cfg = _scratch_host_cfg(tmp_path)
    container_cfg = PathConfig.from_env(_container_env(tmp_path), require_existing=False)
    clone = host_cfg.runs_root / "run-xyz" / "repo"

    request = spawn_wrapper.build_phase_request(
        _PHASE,
        goal="g",
        workdir="/tmp/wt",
        model="deepseek/deepseek-v4-pro",
        spec_name="spec_x",
        image="fleet/base",
        path_config=container_cfg,
        run_clone=str(clone),
    )
    assert request["run_clone"] == str(clone)
    assert request["view"] == launch_broker.VIEW_HOST

    # client-side validate against the container's OWN config (this is the refusal that used to
    # fire at spawn_wrapper step 3 — the f1(b) collision).
    client_errors = spawn_wrapper.validate_spawn(
        request,
        phase_scopes={"p1_slice1_base_supervisor": "implementation"},
        path_config=container_cfg,
    )
    assert client_errors == [], (
        f"client-side validate refused the cs1 container spawn: {client_errors}"
    )

    # broker-side validate + dry-run launch against the HOST config (the executed bind source is
    # always a host path).
    outcome = launch_broker.launch(request, dry_run=True, path_config=host_cfg)
    assert outcome["ok"] is True, outcome
    joined = " ".join(outcome["argv"])
    assert f"-v {clone}:/repo:rw" in joined


def test_the_shared_repo_surface_is_still_refused_for_a_container_view_config(tmp_path):
    """(guard honesty) the cs1 shared-surface refinement does not open a hole: a container-view
    clone request that would mount the SHARED repo tree instead of its own clone is still refused
    — the /repo mount must source the run clone (step 3), and the shared .git/overlay surfaces
    are still refused by target and by source."""
    container_cfg = PathConfig.from_env(_container_env(tmp_path), require_existing=False)
    clone = container_cfg.runs_root / "run-abc" / "repo"

    # (i) a /repo mount that sources the SHARED repo tree, not the clone -> refused
    tampered = spawn_wrapper.build_phase_request(
        _PHASE,
        goal="g",
        workdir="/tmp/wt",
        model="m",
        spec_name="spec_x",
        path_config=container_cfg,
        run_clone=str(clone),
    )
    for m in tampered["mounts"]:
        if m["target"] == "/repo":
            m["source"] = REPO_DIR
    errors = spawn_wrapper.validate_spawn(
        tampered,
        phase_scopes={"p1_slice1_base_supervisor": "implementation"},
        path_config=container_cfg,
    )
    assert errors and any("step 3" in e for e in errors), errors

    # (ii) the shared /repo/.git overlay is still a shared surface for a container-view config
    tampered = spawn_wrapper.build_phase_request(
        _PHASE,
        goal="g",
        workdir="/tmp/wt",
        model="m",
        spec_name="spec_x",
        path_config=container_cfg,
        run_clone=str(clone),
    )
    tampered["mounts"] = list(tampered["mounts"]) + [
        {"target": "/repo/.git", "source": GIT_DIR, "mode": "rw"},
    ]
    errors = spawn_wrapper.validate_spawn(
        tampered,
        phase_scopes={"p1_slice1_base_supervisor": "implementation"},
        path_config=container_cfg,
    )
    assert errors and any("step 3" in e and "shared" in e for e in errors), errors
