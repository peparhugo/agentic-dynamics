"""fb2_broker_hostside — the broker runs where the socket is (fleet_launch_boundary_followups).

The follow-up wave's second half-delivery (F3): the launch broker is deployed as a GENUINELY
host-side component — a systemd user unit running ``launch_broker.py serve`` on a unix-socket
IPC seam — and the orchestrator's spawn path talks to the broker over that seam. The
in-process broker import is gone from the wrapper; NO container mounts the docker socket and NO
in-container code calls docker; the compose orchestrator tier mounts only the typed seam
socket; and a broker-hosted smoke (a synthetic cell spawn request round-tripped through the
host broker) returns an outcome — or, when docker is unavailable, fails loudly with a named
state, never silently.

VERIFY coverage (the wave's fb2 checklist, both directions):

    (a) the broker service file exists and names the broker module (systemd unit content
        asserted);
    (b) the spawn path invokes the broker over the seam — the in-process import is gone
        (the call site is asserted: spawn_wrapper emits via broker_client, never
        launch_broker.launch/submit_run/run_fleet_command);
    (c) no compose service mounts the (docker) socket (grep the yml);
    (d) a broker round-trip with a stubbed docker binary returns the expected outcome;
    (e) docker-unavailable fails loudly with a named state (never a silent pass).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FLEET_DIR = str(_REPO_ROOT / "scripts" / "fleet")
if _FLEET_DIR not in sys.path:
    sys.path.insert(0, _FLEET_DIR)

from scripts.fleet import broker_client, launch_broker, spawn_wrapper  # noqa: E402

#: A phase authorized for the implementation scope so builder-made requests validate cleanly.
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
        command=["python3", "-c", "pass"],
    )
    request.update(overrides)
    return request


# ── (a) the broker service file exists and names the broker module ──────────


def test_launch_broker_service_unit_exists_and_names_the_broker_module():
    """fb2 VERIFY (a): the host-side broker is a committed systemd user unit that runs the
    broker module as a service (``serve`` on the seam socket) — the socket's only home."""
    unit = _REPO_ROOT / "infrastructure" / "agentic-dynamics-launch-broker.service"
    assert unit.is_file(), "the broker systemd user unit must be committed"
    text = unit.read_text()
    # It must run the broker module's serve mode over the seam socket...
    assert "launch_broker.py" in text
    assert "serve" in text
    assert "--socket" in text
    # ...as a host-side USER unit (systemd user semantics), never a container.
    assert "[Unit]" in text and "[Service]" in text and "[Install]" in text
    assert "WantedBy=default.target" in text  # user unit (not multi-user.target = system unit)


def test_service_unit_runs_the_broker_module_that_owns_serve():
    """The unit names the exact module that implements ``serve`` — a rename would break both."""
    unit = _REPO_ROOT / "infrastructure" / "agentic-dynamics-launch-broker.service"
    text = unit.read_text()
    for needle in ("scripts/fleet/launch_broker.py", "launch-broker.sock", "ExecStart="):
        assert needle in text, f"unit must carry {needle!r}"
    # The module it names really does implement serve (no phantom reference).
    assert callable(launch_broker.serve)


# ── (b) the spawn path invokes the broker over the seam — in-process import gone ─


def _ast_names_launch_broker(source: str) -> bool:
    """True when the source imports launch_broker or calls a launch_broker attribute in CODE
    (docstrings/comments excluded — an AST walk sees only real statements)."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "launch_broker" or alias.name.startswith("launch_broker."):
                    return True
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id == "launch_broker":
            return True
    return False


def test_spawn_path_has_no_in_process_broker_import():
    """fb2 VERIFY (b): the in-process import is GONE — the wrapper's code never imports the
    broker module and never calls ``launch_broker.launch``/``submit_run``/``run_fleet_command``.
    (The b3-era call sites spawn_wrapper.py:launch_broker.launch / submit_run /
    run_fleet_command are what F3 found; they are now seam calls.)"""
    src = (_REPO_ROOT / "scripts" / "fleet" / "spawn_wrapper.py").read_text()
    assert not _ast_names_launch_broker(src), (
        "spawn_wrapper must not import or call the broker module in-process (fb2: the docker "
        "call executes only in the host broker's process, reached over the seam)"
    )
    for forbidden in ("launch_broker.launch(", "launch_broker.submit_run(",
                      "launch_broker.run_fleet_command("):
        assert forbidden not in src, forbidden


def test_spawn_path_emits_over_the_seam_client():
    """fb2 VERIFY (b), positive direction: the call sites are the seam client's typed verbs.
    The wrapper builds a BrokerClient (unix-socket seam) and calls launch/submit/
    fleet_command on it — never a docker argv builder, never the broker module."""
    src = (_REPO_ROOT / "scripts" / "fleet" / "spawn_wrapper.py").read_text()
    assert "from broker_client import BrokerClient" in src
    assert "_broker_client().launch(" in src      # spawn_sibling
    assert "_broker_client().submit(" in src      # dispatch_submit
    assert "_broker_client().fleet_command(" in src  # consume_fleet_commands
    # the docker argv builders live in the broker module only.
    assert "def build_launch_argv" not in src
    assert "def build_submit_argv" not in src


def test_spawn_sibling_round_trips_a_synthetic_cell_request_through_the_host_broker(
    broker_seam_stub,
):
    """fb2 VERIFY (d) + the broker-hosted SMOKE: a synthetic cell spawn request round-trips
    through the host broker (a real serve() on a unix socket, a real BrokerClient, a REAL stub
    docker binary) and returns the expected outcome — the stub recorded the argv the broker
    executed, proving the docker call happened in the broker's process."""
    request = _built_request()
    client = broker_client.BrokerClient(broker_seam_stub.socket_path)
    outcome = client.launch(request, dry_run=False)

    assert outcome["ok"] is True
    assert outcome["state"] == launch_broker.STATE_OK
    assert outcome["returncode"] == 0
    # the broker executed its OWN argv through the (stub) docker binary — the recorded argv is
    # the real docker run the broker built from its own profile expansion.
    assert outcome["argv"][0] == broker_seam_stub.docker_bin
    assert "run" in outcome["argv"]

    recorded = _read_log(broker_seam_stub.log)
    assert len(recorded) == 1
    executed = recorded[0]
    # The stub script's own argv starts AFTER its name, so the recorded argv begins at "run".
    assert executed[0] == "run"
    assert "--rm" in executed
    assert any(arg.startswith("-v ") or arg == "-v" for arg in executed)
    assert "fleet-net" in executed  # the typed network made it to the executed argv


def test_spawn_sibling_over_the_seam_returns_the_broker_outcome(broker_seam_stub):
    """spawn_sibling (the orchestrator's spawn path) now reaches the host broker over the seam
    and returns the broker's outcome — the executor's contract is unchanged."""
    outcome = spawn_wrapper.spawn_sibling(_built_request())
    assert outcome["ok"] is True
    assert outcome["state"] in (launch_broker.STATE_OK, launch_broker.STATE_RUN_FAILED)
    assert outcome["argv"][0] == broker_seam_stub.docker_bin
    assert len(_read_log(broker_seam_stub.log)) == 1


def test_broker_unreachable_fails_loudly_never_silently(monkeypatch):
    """A spawn path that cannot reach the host broker (unit down / socket absent) raises a loud
    SpawnValidationError naming the socket — never a silent pass."""
    monkeypatch.setenv("FINOPS_LAUNCH_BROKER_SOCKET", "/nonexistent/launch-broker.sock")
    with pytest.raises(spawn_wrapper.SpawnValidationError) as exc:
        spawn_wrapper.spawn_sibling(_built_request())
    joined = "\n".join(exc.value.errors)
    assert "launch broker is unreachable" in joined
    assert "/nonexistent/launch-broker.sock" in joined


def test_ping_round_trips_through_the_seam(broker_seam_stub):
    outcome = broker_client.BrokerClient(broker_seam_stub.socket_path).ping()
    assert outcome["ok"] is True
    assert outcome["state"] == launch_broker.STATE_PONG


def test_client_frame_is_a_complete_json_object(broker_seam_stub):
    """The seam reply is one complete JSON object per request — the client never parses a
    half-frame or a dropped connection as anything other than an error."""
    outcome = broker_client.BrokerClient(broker_seam_stub.socket_path).ping()
    json.dumps(outcome)  # round-trips


# ── (e) docker-unavailable fails loudly with a named state ───────────────────


def test_docker_unavailable_is_a_named_loud_state(tmp_path, monkeypatch):
    """fb2 VERIFY (e): when the docker binary is missing, the broker replies with the NAMED
    state DOCKER_UNAVAILABLE (never a silent pass), and the spawn path surfaces it loudly."""
    import threading

    from scripts.fleet import launch_broker as lb

    socket_path = str(tmp_path / "nobroker.sock")
    missing_docker = str(tmp_path / "no-such-docker")
    stop = threading.Event()
    ready = threading.Event()
    thread = threading.Thread(
        target=lb.serve,
        kwargs={"socket_path": socket_path, "docker": missing_docker,
                "stop_event": stop, "ready_event": ready},
        daemon=True,
    )
    thread.start()
    assert ready.wait(10)
    try:
        client = broker_client.BrokerClient(socket_path)
        outcome = client.launch(_built_request(), dry_run=False)
        assert outcome["ok"] is False
        assert outcome["state"] == lb.STATE_DOCKER_UNAVAILABLE
        assert "docker is unavailable" in outcome.get("stderr", "")
        assert "DOCKER_UNAVAILABLE" in outcome.get("stderr", "")
    finally:
        stop.set()
        thread.join(timeout=10)


def test_spawn_sibling_surfaces_docker_unavailable_loudly(tmp_path, monkeypatch):
    """The wrapper maps the broker's DOCKER_UNAVAILABLE state onto a loud refusal carrying the
    named state — never a silent pass at the spawn boundary either."""
    import threading

    from scripts.fleet import launch_broker as lb

    socket_path = str(tmp_path / "nobroker2.sock")
    missing_docker = str(tmp_path / "no-such-docker")
    stop = threading.Event()
    ready = threading.Event()
    thread = threading.Thread(
        target=lb.serve,
        kwargs={"socket_path": socket_path, "docker": missing_docker,
                "stop_event": stop, "ready_event": ready},
        daemon=True,
    )
    thread.start()
    assert ready.wait(10)
    monkeypatch.setenv("FINOPS_LAUNCH_BROKER_SOCKET", socket_path)
    try:
        with pytest.raises(spawn_wrapper.SpawnValidationError) as exc:
            spawn_wrapper.spawn_sibling(_built_request())
        joined = "\n".join(exc.value.errors)
        assert "DOCKER_UNAVAILABLE" in joined
        assert "docker is unavailable" in joined
    finally:
        stop.set()
        thread.join(timeout=10)


# ── (c) no compose service mounts the docker socket ──────────────────────────


def test_compose_mounts_no_docker_socket():
    """fb2 VERIFY (c): grep the yml — no compose service mounts the docker socket, and the
    broker seam socket (the typed seam, NOT the docker socket) is the only ``.sock`` anywhere,
    mounted by the orchestrator tier only (covered in detail by test_fleet_guards)."""
    compose = (_REPO_ROOT / "infrastructure" / "docker-compose.ladder.yml").read_text()
    assert "/var/run/docker.sock" not in compose
    assert "docker.sock" not in compose
    assert "launch-broker.sock" in compose  # the typed seam IS present for the orchestrator tier


# ── the systemd unit and serve() are genuinely host-side, not in-container ────


def test_serve_runs_the_broker_module_not_a_container_command():
    """The broker daemon is the python module running on the HOST (the unit's ExecStart is a
    host ``python3 scripts/fleet/launch_broker.py serve``), never a docker/compose command."""
    text = (_REPO_ROOT / "infrastructure" / "agentic-dynamics-launch-broker.service").read_text()
    exec_start = next(
        line.split("=", 1)[1].strip() for line in text.splitlines()
        if line.startswith("ExecStart=")
    )
    assert "python3" in exec_start
    assert "launch_broker.py" in exec_start
    assert "serve" in exec_start
    assert "--socket" in exec_start
    # the unit launches the broker module; it never launches a container to hold the socket.
    assert "docker" not in exec_start.split("python3")[0]
    assert "container" not in exec_start


def _read_log(log_path: str) -> list[list[str]]:
    """The stub binaries' argv records: one argv list per executed stub call.

    Each stub wrote ``echo "$@" >> log``, so every executed argv landed as one space-joined
    line; the docker argv under test carries no embedded spaces (paths, flags, the image, the
    command), so a plain split recovers the argv exactly.
    """
    path = Path(log_path)
    if not path.is_file():
        return []
    return [line.split() for line in path.read_text().splitlines() if line.strip()]
