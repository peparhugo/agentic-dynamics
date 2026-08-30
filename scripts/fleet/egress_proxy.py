#!/usr/bin/env python3
"""The egress proxy — the single internet policy point (proposal §3/D-17).

A cell's reachability is fixed by network membership (``fleet-net``), and its internet
access is fixed by this proxy: the cell/orchestrator scopes set ``HTTP(S)_PROXY`` to it, and
it **allowlists only the model endpoints**. No other egress exists — a cell cannot reach an
arbitrary host, and the model CLIs' traffic is the only traffic the proxy forwards.

Implementation: a threaded forward proxy that handles the two shapes a modern CLI uses:

    * ``CONNECT host:port`` — an HTTPS tunnel (the model APIs are all TLS); the proxy
      checks the CONNECT target host against the allowlist, then opens a blind byte relay
      to the destination (it cannot inspect the TLS payload — policy is at the *host* layer).
    * plain ``GET/POST http://...`` — a legacy/insecure path, forwarded the same way after
      the same allowlist check (and refused unless ``EGRESS_ALLOW_HTTP=1`` is set, since
      model traffic should never be cleartext).

Allowlist (``EGRESS_ALLOWLIST``, comma-separated): exact hostname or ``*.suffix`` wildcards,
defaulting to the opencode/claude/deepseek/anthropic/openai endpoints. A non-matching
host gets a 403 and a log line — the audit trail for the network-policy guard (slice 4).

This file has no repo imports and no external deps (stdlib only) so it runs as a tiny
standalone image/service on ``fleet-net``.
"""

from __future__ import annotations

import os
import select
import socket
import socketserver
from dataclasses import dataclass, field

LISTEN_HOST = os.environ.get("EGRESS_LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("EGRESS_LISTEN_PORT", "8888"))
ALLOW_HTTP = os.environ.get("EGRESS_ALLOW_HTTP", "0") == "1"

# The default model endpoints — the opencode (deepseek/anthropic/openai) + claude API hosts.
_DEFAULT_ALLOWLIST = [
    "api.deepseek.com",
    "api.anthropic.com",
    "api.openai.com",
    "*.anthropic.com",
    "*.deepseek.com",
    "*.openai.com",
]


@dataclass
class Allowlist:
    """A host allowlist with exact + ``*.suffix`` wildcard semantics."""

    exact: set[str] = field(default_factory=set)
    suffixes: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls, raw: str | None = None) -> "Allowlist":
        """Build from ``EGRESS_ALLOWLIST`` (comma-separated), falling back to the defaults."""
        raw = raw if raw is not None else os.environ.get("EGRESS_ALLOWLIST", "")
        entries = [e.strip().lower() for e in raw.split(",") if e.strip()] or _DEFAULT_ALLOWLIST
        wl = cls()
        for e in entries:
            if e.startswith("*."):
                wl.suffixes.append(e[1:])  # store ".suffix" (with the leading dot)
            else:
                wl.exact.add(e)
        return wl

    def allows(self, host: str) -> bool:
        """True if ``host`` (lowercased, port stripped) is permitted."""
        h = host.lower().rsplit(":", 1)[0] if ":" in host else host.lower()
        if h in self.exact:
            return True
        return any(h.endswith(suf) for suf in self.suffixes)


ALLOWLIST = Allowlist.from_env()


def _log(msg: str) -> None:
    print(f"[egress-proxy] {msg}", flush=True)


def _relay(src: socket.socket, dst: socket.socket) -> None:
    """Bidirectionally relay bytes until either side closes (a blind tunnel)."""
    try:
        while True:
            readable, _, _ = select.select([src, dst], [], [], 30.0)
            if not readable:
                break
            for s in readable:
                data = s.recv(65536)
                if not data:
                    return
                (dst if s is src else src).sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.close()
            except OSError:
                pass


class ProxyHandler(socketserver.BaseRequestHandler):
    """One connection — parse the first line, apply policy, then tunnel or refuse."""

    def _refuse(self, host: str) -> None:
        _log(f"DENY {host} (not in allowlist)")
        body = b"403 Forbidden: host not in egress allowlist\n"
        self.request.sendall(
            b"HTTP/1.1 403 Forbidden\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(body)
            + body,
        )

    def _connect(self, host: str, port: int) -> None:
        """CONNECT tunnel: check the host, then relay blindly to the destination."""
        if not ALLOWLIST.allows(host):
            self._refuse(host)
            return
        _log(f"ALLOW {host}:{port} (CONNECT)")
        try:
            upstream = socket.create_connection((host, port), timeout=15)
        except OSError as exc:
            _log(f"CONNECT {host}:{port} failed: {exc}")
            self.request.sendall(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
            return
        self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        _relay(self.request, upstream)

    def handle(self) -> None:
        try:
            first = self.request.recv(65536)
        except OSError:
            return
        if not first:
            return
        line = first.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        parts = line.split()
        if not parts:
            return

        if parts[0] == "CONNECT" and len(parts) >= 2:
            hostport = parts[1]
            host, _, port = hostport.partition(":")
            self._connect(host, int(port) if port else 443)
            return

        # Plain HTTP — refused unless explicitly enabled (model traffic is TLS).
        if not ALLOW_HTTP:
            _log(f"DENY {parts[1] if len(parts) > 1 else '?'} (cleartext HTTP disabled)")
            self.request.sendall(
                b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
            )
            return

        _log(f"DENY {parts[1] if len(parts) > 1 else '?'} (cleartext HTTP forwarding not "
             f"implemented — use CONNECT)")
        self.request.sendall(
            b"HTTP/1.1 501 Not Implemented\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
        )


class ThreadingProxyServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """A threaded TCP server (one thread per tunnel), daemonized so Ctrl-C is clean."""

    allow_reuse_address = True
    daemon_threads = True


def main(argv: list[str] | None = None) -> int:
    _log(f"starting on {LISTEN_HOST}:{LISTEN_PORT} — allowlist "
         f"exact={sorted(ALLOWLIST.exact)} suffixes={ALLOWLIST.suffixes}")
    server = ThreadingProxyServer((LISTEN_HOST, LISTEN_PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
