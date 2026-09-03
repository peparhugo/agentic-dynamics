#!/usr/bin/env python3
"""The launch broker's IPC seam CLIENT (fb2_broker_hostside).

The broker runs where the socket is: a host-side systemd user unit
(``infrastructure/agentic-dynamics-launch-broker.service``) that serves ``launch_broker.py``'s
``serve`` mode on a unix socket. This module is the OTHER half of that seam — the client any
process that needs a cell launched talks through. It is deliberately dependency-free (stdlib
``socket``/``json``/``struct`` only): it never imports the broker module, never builds a docker
argv, and never calls docker, so the orchestrator's spawn path (``spawn_wrapper.py``) can use
it from inside a socketless container and still reach ONLY the host broker's typed, validated
seam.

Protocol (one request per connection, framed):
    frame = 8-byte big-endian length + UTF-8 JSON
    request  = {"verb": "launch"|"submit"|"fleet-command"|"ping", "request": {...},
                "dry_run": bool}
    response = the broker's JSON outcome (always one complete object — a refusal, a
               docker-unavailable state, or a server error is a NAMED state in the object,
               never a dropped connection and never a silent pass).

The client raises :class:`BrokerError` when the SEAM itself fails — the broker unit is down,
the socket is absent, or the reply is not a valid frame. A refused/docker-unavailable reply is
NOT an exception: it comes back as an outcome carrying a ``state`` the caller maps
(``spawn_wrapper`` maps ``REFUSED`` onto its refusal type and surfaces ``DOCKER_UNAVAILABLE``
loudly).
"""

from __future__ import annotations

import json
import os
import socket
import struct
from pathlib import Path
from typing import Any

#: The env var naming the broker's seam socket — the ONE knob every consumer shares. The host
#: side names the socket the systemd unit listens on; a containerized orchestrator names the
#: socket's mount point inside the container. Resolution order in :func:`default_socket_path`.
BROKER_SOCKET_ENV = "FINOPS_LAUNCH_BROKER_SOCKET"

#: The socket file name under the runtime dir / the compose mount target. Kept here (the
#: client's default + the unit's RuntimeDirectory + the compose mount all name the SAME file)
#: so the three deployment surfaces cannot drift.
BROKER_SOCKET_FILENAME = "launch-broker.sock"

#: The default connect timeout (seconds). A broker unit that is down must fail the client in
#: seconds, never hang a spawn. Once connected, reads BLOCK: a ``docker run`` a broker is
#: executing can legitimately take hours, so there is deliberately no read deadline — the
#: broker's reply arrives when the launch finishes.
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5.0


class BrokerError(OSError):
    """The IPC seam failed — the broker is unreachable or replied with a broken frame.

    NEVER a silent pass: a spawn path that cannot reach the broker raises this with the socket
    path + the underlying reason in the message, so a missing/stopped broker unit is a loud,
    diagnosable failure (never "docker succeeded" by absence).
    """


def default_socket_path() -> str:
    """The seam socket path as THIS process sees it.

    Resolution order: the :data:`BROKER_SOCKET_ENV` override (the one knob), then the
    user runtime dir (``XDG_RUNTIME_DIR`` — where the systemd user unit's RuntimeDirectory
    lives, so a host-side orchestrator in the same session finds the unit's socket without
    exporting anything), then the dev fallback under ``/tmp``. A containerized orchestrator
    sets the env var to the seam socket's container mount point.
    """
    override = os.environ.get(BROKER_SOCKET_ENV)
    if override:
        return override
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return str(Path(runtime_dir) / BROKER_SOCKET_FILENAME)
    return f"/tmp/agentic-dynamics-{BROKER_SOCKET_FILENAME}"


def send_frame(sock: socket.socket, obj: Any) -> None:
    """Write one framed JSON object to ``sock`` (8-byte big-endian length + UTF-8 JSON)."""
    payload = json.dumps(obj).encode("utf-8")
    sock.sendall(struct.pack(">Q", len(payload)) + payload)


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise BrokerError("the broker closed the connection mid-frame (empty read)")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def recv_frame(sock: socket.socket) -> Any:
    """Read one framed JSON object from ``sock`` (mirror of :func:`send_frame`)."""
    header = _recv_exact(sock, 8)
    (size,) = struct.unpack(">Q", header)
    if size > (1 << 31):
        raise BrokerError(f"broker frame of {size} bytes exceeds the size bound (2 GiB)")
    payload = _recv_exact(sock, size)
    try:
        return json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BrokerError(f"the broker replied with a malformed frame: {exc}") from exc


class BrokerClient:
    """The typed seam client: send one framed request, receive one framed outcome.

    The client never validates the request and never executes anything — the broker (the
    host-side process that owns the docker socket) re-validates every request with the shared
    contract and performs the docker/compose call itself. A broker-side refusal comes back as
    an outcome with ``state == "REFUSED"`` and an ``errors`` list; docker being unavailable
    comes back as ``state == "DOCKER_UNAVAILABLE"``; both are NAMED states the caller surfaces,
    never a silent pass.
    """

    def __init__(
        self,
        socket_path: str | os.PathLike[str] | None = None,
        *,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    ):
        self.socket_path = str(socket_path) if socket_path is not None else default_socket_path()
        self.connect_timeout = connect_timeout

    def request(
        self,
        verb: str,
        request: dict[str, Any],
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Send ``verb``/``request`` to the broker over the seam and return its outcome dict."""
        payload = {"verb": verb, "request": request or {}, "dry_run": bool(dry_run)}
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(self.connect_timeout)
            try:
                sock.connect(self.socket_path)
            except OSError as exc:
                raise BrokerError(
                    f"the launch broker is unreachable at {self.socket_path}: {exc} — is the "
                    f"agentic-dynamics-launch-broker.service running? (a cell cannot spawn "
                    f"without the host-side broker)"
                ) from exc
            # No read deadline once connected: the broker's reply arrives when the launch it is
            # executing finishes (a docker run can legitimately take hours).
            sock.settimeout(None)
            send_frame(sock, payload)
            outcome = recv_frame(sock)
        if not isinstance(outcome, dict):
            raise BrokerError(
                f"the broker replied with a non-object outcome {type(outcome).__name__!r} "
                f"for verb {verb!r}"
            )
        return outcome

    def launch(self, request: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
        """Round-trip one typed cell launch request to the host broker."""
        return self.request("launch", request, dry_run=dry_run)

    def submit(self, command: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
        """Round-trip one validated ``submit`` command to the host broker."""
        return self.request("submit", command, dry_run=dry_run)

    def fleet_command(self, command: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
        """Round-trip one scale/drain/restart/submit fleet command to the host broker."""
        return self.request("fleet-command", command, dry_run=dry_run)

    def ping(self) -> dict[str, Any]:
        """Round-trip a liveness ping (the broker replies ``state == "PONG"``)."""
        return self.request("ping", {})


def broker_client_from_env() -> BrokerClient:
    """A client bound to the configured seam socket (env resolved at call time)."""
    return BrokerClient()
