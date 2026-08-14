"""Supervise ``claude --bg`` background sessions — roster + owned-session relay only.

Structurally parallel to ``scripts/supervise.py``, but simpler: there is no
AI health-flagging loop here (deferred, see ``docs/spec.md`` §1.1). This
process is the *only* thing that shells out to ``claude agents``/``claude
logs`` on a poll interval — ``admin/server.py`` only reads the Redis keys
this process writes (``claude_bg:roster``, ``claude_bg:cursor:<id>``), so the
single-process Flask dev server never accumulates polling threads.

Ownership boundary: external sessions (present in ``claude agents --json
--all`` but not started via ``POST /api/claude-agents``) are listed in the
roster but are never relayed — this is both a resource bound and a courtesy
boundary (the Control Room does not continuously shell out against a session
an operator started elsewhere without being told to).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "admin"))
sys.path.insert(0, str(ROOT / "src"))

from claude_agents_client import (  # noqa: E402
    CELL_ID_PREFIX,
    CURSOR_KEY_PREFIX,
    OWNED_SESSIONS_KEY,
    ROSTER_KEY,
    ClaudeAgentsClient,
    ClaudeAgentsError,
)

from instrument.live import LivePublisher  # noqa: E402

logger = logging.getLogger("claude_agents_supervisor")

POLL_INTERVAL = float(os.environ.get("CLAUDE_AGENTS_POLL_INTERVAL", "10"))
RELAY_GRACE_SECONDS = float(os.environ.get("CLAUDE_AGENTS_RELAY_GRACE_SECONDS", "120"))
MAX_RELAYS = int(os.environ.get("CLAUDE_AGENTS_MAX_RELAYS", "20"))
REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))

# Statuses the roster JSON is documented to report (docs/spec.md §1.3).
TERMINAL_STATUSES = {"stopped", "completed"}


def _redis():
    import redis

    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)


def _configured_workdirs() -> list[str]:
    """Same ``PATH{pathsep}PATH...`` shape as ``FINOPS_DESIGN_WORKDIRS``."""
    configured = os.environ.get("FINOPS_CLAUDE_AGENT_WORKDIRS")
    if not configured:
        return [str(ROOT)]
    return [item for item in configured.split(os.pathsep) if item]


def _parse_timestamp(value: object) -> float | None:
    """Return epoch seconds for a roster-reported timestamp, or ``None``."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


class ClaudeAgentsSupervisor:
    """Own every polling/relay subprocess call for Claude background sessions."""

    def __init__(
        self,
        *,
        client: ClaudeAgentsClient | None = None,
        redis_factory=_redis,
        workdirs: list[str] | None = None,
    ) -> None:
        self.client = client or ClaudeAgentsClient()
        self.redis_factory = redis_factory
        self.workdirs = workdirs if workdirs is not None else _configured_workdirs()
        self._relay_threads: dict[str, threading.Thread] = {}
        self._relay_stop: dict[str, threading.Event] = {}
        self._lock = threading.RLock()

    def refresh_roster(self) -> list[dict]:
        """Poll every configured workdir once, merge by id, and publish the roster."""
        redis_client = self.redis_factory()
        merged: dict[str, dict] = {}
        for workdir in self.workdirs:
            try:
                entries = self.client.list_agents(workdir, all=True)
            except ClaudeAgentsError as error:
                logger.warning("claude agents --json --all --cwd %s failed: %s", workdir, error)
                continue
            for entry in entries:
                merged[entry["id"]] = entry

        try:
            owned_ids = set(redis_client.smembers(OWNED_SESSIONS_KEY))
        except Exception as error:  # noqa: BLE001 - a stale roster beats a dead supervisor
            logger.warning("could not read %s: %s", OWNED_SESSIONS_KEY, error)
            owned_ids = set()

        candidates = self._relay_candidates(merged, owned_ids)
        relayed_ids = self._reconcile_relays(candidates)

        roster = [
            {**entry, "id": session_id, "owned": session_id in owned_ids, "relay_active": session_id in relayed_ids}
            for session_id, entry in merged.items()
        ]
        try:
            redis_client.set(ROSTER_KEY, json.dumps(roster, separators=(",", ":")), ex=max(1, int(2 * POLL_INTERVAL)))
        except Exception as error:  # noqa: BLE001
            logger.warning("could not write %s: %s", ROSTER_KEY, error)
        return roster

    def _relay_candidates(self, merged: dict[str, dict], owned_ids: set[str]) -> list[dict]:
        """Owned sessions that are running, or terminal within the grace window."""
        now = time.time()
        candidates = []
        for session_id, entry in merged.items():
            if session_id not in owned_ids:
                continue
            status = str(entry.get("status", "")).lower()
            if status not in TERMINAL_STATUSES:
                candidates.append(entry)
                continue
            updated_at = _parse_timestamp(entry.get("updated_at") or entry.get("started_at"))
            if updated_at is not None and now - updated_at < RELAY_GRACE_SECONDS:
                candidates.append(entry)
        candidates.sort(key=lambda entry: _parse_timestamp(entry.get("updated_at")) or 0.0, reverse=True)
        return candidates

    def _reconcile_relays(self, candidates: list[dict]) -> set[str]:
        """Start relays for newly-wanted sessions; stop ones no longer wanted.

        The roster itself lists every owned session regardless of relay status;
        only the overflow past ``MAX_RELAYS`` is logged, never silently dropped.
        """
        wanted = candidates[:MAX_RELAYS]
        overflow = candidates[MAX_RELAYS:]
        if overflow:
            logger.warning(
                "claude-agents relay at capacity (%d); %d owned session(s) not relayed this tick: %s",
                MAX_RELAYS,
                len(overflow),
                [entry["id"] for entry in overflow],
            )
        wanted_ids = {entry["id"] for entry in wanted}

        with self._lock:
            for session_id, thread in list(self._relay_threads.items()):
                if not thread.is_alive():
                    del self._relay_threads[session_id]
                    self._relay_stop.pop(session_id, None)
            for session_id in list(self._relay_threads):
                if session_id not in wanted_ids:
                    stop_event = self._relay_stop.get(session_id)
                    if stop_event is not None:
                        stop_event.set()
            for entry in wanted:
                session_id = entry["id"]
                if session_id in self._relay_threads:
                    continue
                stop_event = threading.Event()
                self._relay_stop[session_id] = stop_event
                thread = threading.Thread(
                    target=self._relay_session,
                    args=(session_id, stop_event),
                    daemon=True,
                    name=f"claude-bg-{session_id}",
                )
                self._relay_threads[session_id] = thread
                thread.start()
            return {session_id for session_id, thread in self._relay_threads.items() if thread.is_alive()}

    def _relay_session(self, session_id: str, stop_event: threading.Event) -> None:
        """Loop: fetch logs, diff against a persisted line cursor, publish new lines."""
        redis_client = self.redis_factory()
        cursor_key = f"{CURSOR_KEY_PREFIX}{session_id}"
        publisher = LivePublisher(f"{CELL_ID_PREFIX}{session_id}")
        if publisher.enabled:
            publisher.set_status("running")
        try:
            while True:
                self._relay_once(session_id, redis_client, cursor_key, publisher)
                if stop_event.wait(POLL_INTERVAL):
                    # One final poll picks up any output produced right before the
                    # grace period elapsed, then the relay exits.
                    self._relay_once(session_id, redis_client, cursor_key, publisher)
                    break
        finally:
            if publisher.enabled:
                publisher.set_status("done")

    def _relay_once(self, session_id: str, redis_client, cursor_key: str, publisher: LivePublisher) -> int:
        """Publish only the lines new since the last poll; return the count published."""
        try:
            cursor = int(redis_client.get(cursor_key) or 0)
        except Exception:  # noqa: BLE001
            cursor = 0
        try:
            logs = self.client.get_logs(session_id)
        except ClaudeAgentsError as error:
            logger.warning("claude logs %s failed: %s", session_id, error)
            return 0
        lines = logs.splitlines()
        new_lines = lines[cursor:]
        if not new_lines:
            return 0
        for line in new_lines:
            publisher.publish_event({"type": "text", "part": {"text": line}})
        with suppress(Exception):
            redis_client.set(cursor_key, str(len(lines)))
        return len(new_lines)


def log(msg: str) -> None:
    print(f"[claude-agents-supervisor] {msg}", flush=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[claude-agents-supervisor] %(message)s")
    parser = argparse.ArgumentParser(description="Poll claude --bg sessions and relay owned transcripts.")
    parser.add_argument("--once", action="store_true", help="run one roster refresh pass and exit")
    args = parser.parse_args()

    supervisor = ClaudeAgentsSupervisor()
    log(f"polling every {POLL_INTERVAL}s across {len(supervisor.workdirs)} workdir(s); max {MAX_RELAYS} relays")
    while True:
        try:
            roster = supervisor.refresh_roster()
            log(f"roster: {len(roster)} session(s), {sum(1 for e in roster if e['owned'])} owned")
        except Exception as error:  # noqa: BLE001 - a supervisor crash must not orphan relay threads silently
            log(f"roster refresh error: {error!r}")
        if args.once:
            return
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
