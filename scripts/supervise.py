"""Supervise running opencode sessions via a flash monitor session — FLAG only, never steer.

The monitor is a dedicated flash opencode session (created through the same native
API the Control Room uses), so it is "just another session" in the fleet — observable,
costed, and itself a first-class cell. This feeder polls the running sessions, micro-
batches their recent activity, sends each batch to the monitor session, and harvests the
monitor's verdicts (STATUS + WHY) as flags for human review.

No steering, no interrupt: flags only. A human decides the intervention.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "admin"))
sys.path.insert(0, str(ROOT / "src"))

from opencode_client import OpenCodeClient, OpenCodeError  # noqa: E402

from instrument.live import LivePublisher  # noqa: E402

BASE_URL = os.environ.get("OPENCODE_BASE_URL", "http://127.0.0.1:4096")
MONITOR_MODEL = os.environ.get("SUPERVISOR_MODEL", "deepseek/deepseek-v4-flash")
POLL_INTERVAL = int(os.environ.get("SUPERVISOR_POLL_INTERVAL", "60"))
ACTIVE_WINDOW = int(os.environ.get("SUPERVISOR_ACTIVE_WINDOW", "900"))  # seconds
BATCH_EVENTS = int(os.environ.get("SUPERVISOR_BATCH_EVENTS", "12"))
RELAY = os.environ.get("SUPERVISOR_RELAY", "1") == "1"
RELAY_WAIT = float(os.environ.get("SUPERVISOR_RELAY_WAIT", "1.0"))  # bounded stream window
RELAY_WAIT_FIRST = float(os.environ.get("SUPERVISOR_RELAY_WAIT_FIRST", "8.0"))  # first-seen catch-up
FLAGS_FILE = ROOT / "experiments" / "results" / "supervisor" / "flags.jsonl"
STATE_FILE = ROOT / "experiments" / "results" / "supervisor" / "monitor_session.json"

MONITOR_ROLE = (
    "You are the session supervisor. You will receive batches of recent activity from "
    "running AI coding sessions. For each batch, assess the session as one of: "
    "healthy (making forward progress), stalled (no forward progress), or off_track "
    "(drifting from its task, error-looping, or doing the wrong thing).\n"
    "Reply with EXACTLY two lines and nothing else:\n"
    "STATUS: healthy|stalled|off_track\n"
    "WHY: <one concise sentence>\n"
    "You only flag for human review. Never recommend steering or interrupting."
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[supervise] {msg}", flush=True)


def ensure_monitor(client: OpenCodeClient, location: str) -> str:
    """Create or reuse the flash monitor session; return its session id."""
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
            return state["session_id"]
        except (json.JSONDecodeError, KeyError):
            pass
    session = client.create_session(location=location, model=MONITOR_MODEL)
    session_id = session.get("id") or session.get("sessionID")
    if session_id is None and isinstance(session.get("data"), dict):
        session_id = session["data"].get("id") or session["data"].get("sessionID")
    if not session_id:
        raise OpenCodeError(f"create_session returned no id: {list(session)}")
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"session_id": session_id, "model": MONITOR_MODEL}))
    client.send_input(session_id, MONITOR_ROLE, delivery="queue")
    log(f"monitor session created: {session_id}")
    return session_id


def active_sessions(client: OpenCodeClient, *, skip: str | None = None) -> list[dict]:
    """Sessions updated within ACTIVE_WINDOW, excluding the monitor itself."""
    resp = client._json_request("GET", "/api/session", None)
    data = resp.get("data") or []
    cutoff_ms = int(time.time() * 1000) - ACTIVE_WINDOW * 1000
    out = []
    for s in data:
        sid = s.get("id", "")
        if skip and sid == skip:
            continue
        updated = (s.get("time") or {}).get("updated", 0)
        if updated >= cutoff_ms:
            out.append(s)
    return out


def _text_from_messages(resp: dict, limit: int) -> str:
    """Flatten recent message texts into a compact string."""
    lines: list[str] = []
    for m in (resp.get("data") or resp.get("messages") or [])[-limit:]:
        role = m.get("role", "?")
        for part in (m.get("parts") or m.get("content") or []):
            if isinstance(part, str):
                text = part
            elif isinstance(part, dict):
                text = part.get("text") or part.get("reasoning") or ""
            else:
                text = ""
            if text:
                lines.append(f"{role}: {text[:200]}")
    return "\n".join(lines) if lines else "(no recent messages)"


def read_reply(client: OpenCodeClient, session_id: str, *, wait_s: float = 60.0) -> str:
    """Poll the monitor's messages until a new assistant reply appears (best-effort)."""
    deadline = time.time() + wait_s
    last = ""
    while time.time() < deadline:
        try:
            resp = client.messages(session_id)
        except OpenCodeError:
            time.sleep(5)
            continue
        parts = resp.get("data") or resp.get("messages") or []
        if parts:
            last_msg = parts[-1]
            role = last_msg.get("role", "")
            for part in (last_msg.get("parts") or last_msg.get("content") or []):
                text = part.get("text") if isinstance(part, dict) else part
                if role == "assistant" and text and text.strip() != last:
                    return text
        time.sleep(5)
    return ""


def parse_verdict(reply: str) -> tuple[str, str]:
    status, why = "unknown", reply.strip()[:200] or "(no reply)"
    for line in reply.splitlines():
        if line.upper().startswith("STATUS:"):
            status = line.split(":", 1)[1].strip().lower()
        elif line.upper().startswith("WHY:"):
            why = line.split(":", 1)[1].strip()
    return status, why


def _slugify(value: str) -> str:
    out = "".join(ch if ch.isalnum() else "_" for ch in value).strip("_").lower()
    return out[:50] or "session"


def _cell_id_for(session: dict) -> str:
    """A readable Redis cell id for a native session, e.g. live_gpt_5_6_sol_facelift."""
    model = (session.get("model") or {}).get("id", "?")
    title = session.get("title") or ""
    return f"live_{_slugify(model)}_{_slugify(title)}"


def _event_sequence(event: dict) -> str | None:
    for src in (event, event.get("properties") if isinstance(event.get("properties"), dict) else {}):
        for key in ("sequence", "aggregateSequence", "aggregate_sequence", "_sse_id"):
            v = src.get(key)
            if isinstance(v, (str, int)) and not isinstance(v, bool):
                return str(v)
    return None


def relay_once(client: OpenCodeClient, cursors: dict[str, str]) -> None:
    """Bridge each active native session's events into Redis (Control Room stream).

    Uses a bounded SSE read: a daemon thread consumes iter_events for RELAY_WAIT
    seconds, events are published under ``live_<model>_<title>`` and the cell is
    registered in ``story_status`` so it shows in the fleet.
    """
    if not RELAY:
        return
    for s in active_sessions(client):
        sid = s.get("id", "")
        cell_id = _cell_id_for(s)
        after = cursors.get(sid)
        first = after is None
        collected: list[dict] = []

        def consume(sid=sid, after=after, collected=collected) -> None:
            try:
                for ev in client.iter_events(sid, after=after):
                    collected.append(ev)
            except OpenCodeError:
                pass

        t = threading.Thread(target=consume, daemon=True)
        t.start()
        t.join(timeout=RELAY_WAIT_FIRST if first else RELAY_WAIT)

        if not collected:
            continue
        last_seq = next((s2 for e in collected if (s2 := _event_sequence(e))), None)
        if last_seq:
            cursors[sid] = last_seq
        if first:
            continue  # discard replayed history; stream only new events from here on
        publisher = LivePublisher(cell_id)
        if publisher.enabled:
            publisher.set_status("running")
        for ev in collected:
            publisher.publish_event(ev)


def emit_flag(session: dict, status: str, why: str) -> None:
    flag = {
        "at": now(),
        "session_id": session.get("id", ""),
        "title": session.get("title", "")[:80],
        "model": (session.get("model") or {}).get("id", "?"),
        "status": status,
        "why": why,
    }
    FLAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FLAGS_FILE, "a") as f:
        f.write(json.dumps(flag) + "\n")
    print(f"[FLAG] {status}: {flag['title']} — {why}", flush=True)


def supervise_once(client: OpenCodeClient, monitor_id: str, location: str) -> None:
    sessions = active_sessions(client, skip=monitor_id)
    if not sessions:
        log("no active sessions")
        return
    for s in sessions:
        sid = s.get("id", "")
        title = s.get("title", "")[:60]
        try:
            msgs = client.messages(sid)
        except OpenCodeError:
            continue
        text = _text_from_messages(msgs, BATCH_EVENTS)
        if not text.strip():
            continue
        batch = (
            f"SESSION: {title}\n"
            f"MODEL: {(s.get('model') or {}).get('id', '?')}\n"
            f"RECENT ACTIVITY (newest last):\n{text}\n\n"
            "Assess and reply STATUS + WHY."
        )
        try:
            client.send_input(monitor_id, batch, delivery="queue")
            reply = read_reply(client, monitor_id, wait_s=45.0)
        except OpenCodeError as e:
            log(f"monitor error for {title}: {e}")
            continue
        status, why = parse_verdict(reply)
        if status not in ("healthy", "unknown"):
            emit_flag(s, status, why)


def main() -> None:
    ap = argparse.ArgumentParser(description="Flash session supervisor — flag only, never steer.")
    ap.add_argument("--once", action="store_true", help="run one assessment pass and exit")
    ap.add_argument("--location", default=str(ROOT), help="repo location for the monitor session")
    args = ap.parse_args()

    client = OpenCodeClient(BASE_URL)
    monitor_id = ensure_monitor(client, args.location)
    cursors: dict[str, str] = {}
    log(f"relaying + monitoring (assess every {POLL_INTERVAL}s); flags -> {FLAGS_FILE}")

    last_assess = 0.0
    while True:
        try:
            relay_once(client, cursors)
        except Exception as e:  # noqa: BLE001
            log(f"relay error: {e!r}")
        if time.time() - last_assess >= POLL_INTERVAL:
            try:
                supervise_once(client, monitor_id, args.location)
            except Exception as e:  # noqa: BLE001
                log(f"error: {e!r}")
            last_assess = time.time()
        if args.once:
            return
        time.sleep(2)


if __name__ == "__main__":
    main()
