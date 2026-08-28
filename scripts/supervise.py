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
import hashlib
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "control_room"))
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from clients.opencode_client import OpenCodeClient, OpenCodeError  # noqa: E402

from agentic_dynamics.control.live import LivePublisher  # noqa: E402
from agentic_dynamics.control.supervisor import (  # noqa: E402
    SUPERVISOR_FLAGS_KEY,
    SUPERVISOR_FLAGS_MAX,
    SUPERVISOR_SESSION_CELLS_KEY,
    canonical_json,
    parse_mapping,
)

BASE_URL = os.environ.get("OPENCODE_BASE_URL", "http://127.0.0.1:4096")
MONITOR_MODEL = os.environ.get("SUPERVISOR_MODEL", "deepseek/deepseek-v4-flash")
POLL_INTERVAL = int(os.environ.get("SUPERVISOR_POLL_INTERVAL", "60"))
ACTIVE_WINDOW = int(os.environ.get("SUPERVISOR_ACTIVE_WINDOW", "900"))  # seconds
BATCH_EVENTS = int(os.environ.get("SUPERVISOR_BATCH_EVENTS", "12"))
RELAY = os.environ.get("SUPERVISOR_RELAY", "0") == "1"  # off by default: FINOPS_CELL_ID supersedes it
FLAGS_FILE = ROOT / "experiments" / "results" / "supervisor" / "flags.jsonl"
STATE_FILE = ROOT / "experiments" / "results" / "supervisor" / "monitor_session.json"

MONITOR_ROLE = (
    "You are the session supervisor. Your baseline is the game board — read "
    "agent_config/system_snapshot.md (the L0 snapshot: what is running, what it has cost, "
    "what each campaign claims to do, the recent chronological history) before assessing. "
    "You will receive batches of recent activity from running AI coding sessions. For each "
    "batch, assess the session as one of: healthy (making forward progress toward its "
    "declared goal), stalled (no forward progress), or off_track (drifting from its task, "
    "error-looping, doing the wrong thing, or moving in circles).\n"
    "Ground each assessment in four lenses, reading the repo's chronological history "
    "(git log across branches; the discarded-trees ledger "
    "experiments/results/workflows/<spec>/discarded_trees.jsonl) when the activity is "
    "unclear:\n"
    "1. ON-TASK — does the activity advance the campaign's declared goal in the snapshot?\n"
    "2. SAFETY — is anything security-sensitive or destructive happening (deploy commands "
    "outside deploy_allowed phases, secrets, force pushes, tree resets)?\n"
    "3. BUDGET — is the session's cost running away relative to the snapshot's campaign "
    "envelope or the $30-style stop?\n"
    "4. LOOPS — is the session repeating subjects, re-presenting discarded trees, or "
    "re-covering ground a prior campaign covered (the chronology's signature)?\n"
    "Reply with EXACTLY two lines and nothing else:\n"
    "STATUS: healthy|stalled|off_track\n"
    "WHY: <one concise sentence, naming the lens (on-task/safety/budget/loops) when it applies>\n"
    "You only flag for human review. Never recommend steering or interrupting."
)


def now() -> str:
    """Return canonical UTC for durable flag and mapping metadata."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _redis():
    """Construct the framework Redis client lazily so file-only mode still works."""
    import redis

    return redis.Redis(
        host=os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1"),
        port=int(os.environ.get("FINOPS_REDIS_PORT", "6380")),
        db=int(os.environ.get("FINOPS_REDIS_DB", "1")),
        decode_responses=True,
        socket_connect_timeout=2,
    )


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
    """Build a readable, collision-resistant Redis cell ID for one relay."""
    model = (session.get("model") or {}).get("id", "?")
    title = session.get("title") or ""
    native_id = str(session.get("id", ""))
    suffix = hashlib.sha256(native_id.encode()).hexdigest()[:8]
    return f"live_{_slugify(model)}_{_slugify(title)}_{suffix}"


def _relay_session(client: OpenCodeClient, sid: str, cell_id: str) -> None:
    """Stream one native session's durable events into Redis until it ends.

    A full-history replay on first connect is acceptable: LivePublisher caps the
    retained list (ltrim), so the burst is bounded, and the Control Room's terminal
    replays the same retained window. After replay the stream goes live.
    """
    publisher = LivePublisher(cell_id, mapping_source="supervisor_relay")
    publisher.register_session(sid)
    if publisher.enabled:
        publisher.set_status("running")
    try:
        for ev in client.iter_events(sid):
            publisher.publish_event(ev)
    except OpenCodeError:
        pass
    finally:
        if publisher.enabled:
            publisher.set_status("done")


def relay_once(client: OpenCodeClient, threads: dict[str, threading.Thread], finished: set[str]) -> None:
    """Maintain one persistent relay thread per active native session."""
    if not RELAY:
        return
    active = {s["id"]: s for s in active_sessions(client)}
    for sid, s in active.items():
        if sid in threads or sid in finished:
            continue
        cell_id = _cell_id_for(s)
        t = threading.Thread(target=_relay_session, args=(client, sid, cell_id), daemon=True)
        t.start()
        threads[sid] = t
    for sid in list(threads):
        if not threads[sid].is_alive():
            del threads[sid]
            finished.add(sid)


def emit_flag(session: dict, status: str, why: str) -> None:
    """Persist one assessment durably, then update the bounded Redis hot path."""
    flag = {
        "at": now(),
        "session_id": session.get("id", ""),
        "title": session.get("title", "")[:80],
        "model": (session.get("model") or {}).get("id", "?"),
        "status": status,
        "why": why,
    }
    redis_client = None
    try:
        redis_client = _redis()
        mapping = parse_mapping(redis_client.hget(SUPERVISOR_SESSION_CELLS_KEY, flag["session_id"]))
        if mapping:
            # The immutable snapshot keeps file fallback reviewable after a
            # Redis restart without guessing a stream from title or model.
            flag["review"] = mapping
            flag["last_activity_at"] = mapping.get("last_activity_at")
    except Exception:
        redis_client = None

    payload = canonical_json(flag)
    FLAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FLAGS_FILE, "a", encoding="utf-8") as f:
        f.write(payload + "\n")
    try:
        redis_client = redis_client or _redis()
        redis_client.lpush(SUPERVISOR_FLAGS_KEY, payload)
        redis_client.ltrim(SUPERVISOR_FLAGS_KEY, 0, SUPERVISOR_FLAGS_MAX - 1)
    except Exception:
        # JSONL and stdout remain useful when framework Redis is unavailable.
        pass

    # canonical-state round 2 (Delta 1), plan step 13: register this flag in the
    # canonical-state registry too — the session-scoped "newest wins" derivative of the
    # observation supervise_once() already registered for every verdict (this function is
    # only ever called for the non-healthy/unknown subset). Same FINOPS_KB_WRITE-gated,
    # best-effort convention as the lpush/ltrim push just above — a downed DB2 knowledge
    # stream must never cost this function its durable flags.jsonl write or its stdout
    # line, both of which already succeeded by this point.
    if os.environ.get("FINOPS_KB_WRITE") == "1":
        try:
            from agentic_dynamics.control.observation_ingestion import derive_flag_record
            from agentic_dynamics.knowledge import knowledge_stream as ks
            from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID

            record = derive_flag_record(flag, repository_id=REPOSITORY_ID)
            ks.register_records([record], fail_loud=False)
        except Exception as e:  # noqa: BLE001
            log(f"registry emit error for flag {flag.get('session_id', '?')}: {e!r}")

    print(f"[FLAG] {status}: {flag['title']} — {why}", flush=True)


def running_cells(redis_client) -> list[str]:
    """Running workflow cells (wf_*) from the story_status hash, newest first."""
    statuses = redis_client.hgetall("story_status")
    return sorted(
        (cid for cid, st in statuses.items() if cid.startswith("wf_") and st == "running"),
        reverse=True,
    )


def _cell_activity(redis_client, cell_id: str, limit: int) -> str:
    """Recent activity text from a cell's retained event log (Redis, not opencode API)."""
    try:
        events = redis_client.lrange(f"events_log:{cell_id}", -limit, -1)
    except Exception:
        return ""
    lines: list[str] = []
    for raw in events:
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        etype = ev.get("type", "event")
        part = ev.get("part") or {}
        text = ""
        if isinstance(part, dict):
            text = part.get("text") or part.get("reasoning") or ""
            if not text and part.get("tool"):
                state = part.get("state") or {}
                inp = state.get("input") if isinstance(state, dict) else None
                detail = ""
                if isinstance(inp, dict):
                    detail = inp.get("filePath") or inp.get("command") or inp.get("pattern") or ""
                text = f"tool:{part.get('tool', '?')} {str(detail)[:80]}".strip()
        if text:
            lines.append(f"{etype}: {text[:200]}")
    return "\n".join(lines) if lines else ""


KNOWN_CELL_MODELS = {
    "openai_gpt_5_6_sol": "openai/gpt-5.6-sol",
    "openai_gpt_5_6_luna": "openai/gpt-5.6-luna",
    "openai_gpt_5_6_terra": "openai/gpt-5.6-terra",
    "deepseek_deepseek_v4_pro": "deepseek/deepseek-v4-pro",
    "deepseek_deepseek_v4_flash": "deepseek/deepseek-v4-flash",
    "anthropic_claude_fable_5": "anthropic/claude-fable-5",
    "anthropic_claude_haiku_4_5": "anthropic/claude-haiku-4-5",
    "anthropic_claude_sonnet_5": "anthropic/claude-sonnet-5",
}


def cell_model(cell_id: str) -> str:
    for slug, model in KNOWN_CELL_MODELS.items():
        if slug in cell_id:
            return model
    return "unknown"


def supervise_once(client: OpenCodeClient, monitor_id: str, redis_client) -> None:
    """Assess running workflow cells from their Redis event stream (flag only).

    The opencode server API does not expose ``opencode run`` transcripts (messages/
    history are empty), so the assessment reads the events that ``run_workflow``
    publishes under each ``wf_*`` cell via FINOPS_CELL_ID — the same stream the
    Control Room terminal renders.
    """
    cells = running_cells(redis_client)
    if not cells:
        return
    for cell_id in cells:
        text = _cell_activity(redis_client, cell_id, BATCH_EVENTS)
        if not text.strip():
            continue
        model = cell_model(cell_id)
        batch = (
            f"CELL: {cell_id}\n"
            f"MODEL: {model}\n"
            f"RECENT ACTIVITY (newest last):\n{text}\n\n"
            "Assess and reply STATUS + WHY."
        )
        try:
            client.send_input(monitor_id, batch, delivery="queue")
            reply = read_reply(client, monitor_id, wait_s=45.0)
        except OpenCodeError as e:
            log(f"monitor error for {cell_id}: {e}")
            continue
        status, why = parse_verdict(reply)

        # canonical-state round 2 (Delta 1 + round-1 OQ6a), plan step 13: register
        # EVERY verdict — not only the ones that go on to emit a flag below. This is the
        # literal fix for the audit gap round 1 found: a "healthy" verdict previously
        # left no durable trace anywhere, because emit_flag() below was (and still is —
        # the conditional is UNCHANGED) only ever called for a non-healthy/unknown
        # status. Gated on FINOPS_KB_WRITE, same opt-in convention as every other KB
        # writer. UNLIKE story.py/run.py/finalize_reviews.py's inline emits, this one IS
        # wrapped in a try/except: supervise_once() sits inside a live, always-running
        # relay+assess loop (main()'s `while True`), and this is the one call site in the
        # whole plan that touches currently-live production traffic — crashing the
        # entire assessment pass because the separate DB2 knowledge stream happens to be
        # briefly unreachable would take down the flag-only supervisor's actual job for
        # every OTHER cell in this same batch too. This mirrors emit_flag()'s own
        # existing best-effort treatment of ITS Redis push, just below.
        if os.environ.get("FINOPS_KB_WRITE") == "1":
            try:
                from agentic_dynamics.control.observation_ingestion import derive_observation_record
                from agentic_dynamics.knowledge import knowledge_stream as ks
                from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID

                record = derive_observation_record(
                    {"cell_id": cell_id, "status": status, "why": why, "model": model},
                    repository_id=REPOSITORY_ID,
                )
                ks.register_records([record], fail_loud=False)
            except Exception as e:  # noqa: BLE001
                log(f"registry emit error for {cell_id}: {e!r}")

        if status not in ("healthy", "unknown"):     # UNCHANGED — still gates flag emission only
            emit_flag({"id": cell_id, "title": cell_id, "model": {"id": model}}, status, why)


def main() -> None:
    ap = argparse.ArgumentParser(description="Flash session supervisor — flag only, never steer.")
    ap.add_argument("--once", action="store_true", help="run one assessment pass and exit")
    ap.add_argument("--location", default=str(ROOT), help="repo location for the monitor session")
    args = ap.parse_args()

    client = OpenCodeClient(BASE_URL)
    monitor_id = ensure_monitor(client, args.location)
    redis_client = _redis()
    threads: dict[str, threading.Thread] = {}
    finished: set[str] = set()
    log(f"relaying + monitoring (assess every {POLL_INTERVAL}s); flags -> {FLAGS_FILE}")

    last_assess = 0.0
    while True:
        try:
            relay_once(client, threads, finished)
        except Exception as e:  # noqa: BLE001
            log(f"relay error: {e!r}")
        if time.time() - last_assess >= POLL_INTERVAL:
            try:
                supervise_once(client, monitor_id, redis_client)
            except Exception as e:  # noqa: BLE001
                log(f"error: {e!r}")
            last_assess = time.time()
        if args.once:
            return
        time.sleep(2)


if __name__ == "__main__":
    main()
