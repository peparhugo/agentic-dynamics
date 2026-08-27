"""Server-level orphan sweep (cap_runner_hardening2 §Gap 1) — FLAG-ONLY, never steer.

The terra post-mortem's F1 measured the gap this module closes: the one verified
43.4-minute stall was NOT a silent model — it was an **orphaned delegation**. The authoring
session (in the opencode server) spawned a ``task`` subagent; the parent session died
mid-delegation; the subagent **completed** but its result was never reaped. Nothing in the
machine noticed for 43 minutes. The runner-level watchdog cannot see this case: it watches
the runner's own agent process's transcript, and a dead parent is a process exit, not a
stall. The orphan lives in the **opencode server layer** (session + spawned-task state),
which this sweep observes directly.

**Observation surface:** the opencode server's session store — the SQLite ``session`` /
``part`` tables the Control Room's supervisor rail already reads. A subagent is a session
whose ``parent_id`` points at its parent session; the delegation itself is recorded as a
``tool`` part of type ``task`` in the parent whose ``state.metadata.sessionId`` names the
subagent. The sweep reads this store **read-only**.

**Detection (deterministic on transcript timestamps):** a task is an **orphan** when
(a) the parent session has NO *meaningful* part after the task's spawn time (the parent went
silent right after delegating) AND (b) the subagent session/process has terminated — it has a
``step-finish`` part (completed, result produced) or it has produced no ``step-finish`` and
been silent for ``crash_grace_s`` (crashed/zombie). ``idle_minutes`` counts from the
subagent's termination — how long the produced-but-never-reaped result has been sitting.

**Action (flag-only, per the supervisor discipline and the campaign's hard rule 2):** the
sweep (1) records the orphan on the durable ledger
(``experiments/results/orphans/orphans.jsonl``) + the bounded Redis hot list, as a **dated,
flagged** event; (2) reaps the orphaned subagent's *process* if still alive (zombie reaping
only — SIGTERM of a process whose cmdline references the subagent session); and (3) surfaces
the record. It NEVER restarts, retries, resumes, or steers a session: there is deliberately
no code path that can call ``send_input``/``interrupt``/``resume`` — this module imports no
OpenCode client and holds no handle on one (guarded by ``tests/test_orphan_sweep.py``).

**Cadence:** the companion daemon ``scripts/orphan_sweep.py`` runs the sweep on a
configurable interval (default 5 minutes, ``ORPHAN_SWEEP_INTERVAL``). Detection itself is
pure — a function of the transcript timestamps + ``now`` — so it is testable with synthetic
fixtures in both directions, and the terra orphan is replayed as the regression proof
(``tests/fixtures/terra_orphan_snapshot.json``, reconstructed from the live session store).

A documented boundary (the p4 adversarial phase probes it): the completed-subagent arm is a
pure timestamp rule with no stability grace — a live parent that spawned a subagent which
completed *and* the sweep happens to observe in the narrow window before the parent's next
step would be flagged once. The parent-silence arm (no meaningful part after spawn) is the
guard that keeps any genuinely working parent out, and the next cycle self-heals (the parent
now has a step after spawn, so it is no longer an orphan); recording is de-duplicated by
``orphan_id`` so a transient flag never floods the ledger.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import signal
import sqlite3
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_dynamics.control.supervisor import canonical_json, utc_now

#: Default sweep cadence (seconds) — the design doc's "configurable sweep (default 5 min)".
SWEEP_INTERVAL_S = 300
#: Default crash-grace (seconds): a subagent with no ``step-finish`` that has produced no
#: part for this long is treated as crashed/zombie. A recently-active subagent is "running".
CRASH_GRACE_S = 300
#: Redis hot-list key + bound for the surfaced orphan records (mirrors supervisor_flags).
ORPHAN_EVENTS_KEY = "orphan_events"
ORPHAN_EVENTS_MAX = 200

#: The session-transcript part types that count as a *meaningful* parent step — the sweep's
#: "parent has no step after the task's spawn time" reads ONLY these (mirroring the merged
#: phase watchdog's `_MEANINGFUL_EVENT_TYPES`: a junk heartbeat that is not real progress
#: must not rescue a dead delegation — cap_runner_hardening2 p5 probes exactly this).
MEANINGFUL_STEP_TYPES: frozenset[str] = frozenset(
    {"step-start", "step-finish", "tool", "text", "reasoning", "patch"}
)


def _iso_from_ms(ms: int | None) -> str:
    """Render an ms-epoch transcript timestamp as canonical UTC ISO at second granularity.

    The sweep's own detection runs on raw milliseconds (the ``> spawn`` ordering needs the
    sub-second precision); the rendered evidence labels match the post-mortem's documented
    precision (``2026-08-26T21:11:02Z``), so a sub-second fraction is dropped, not kept.
    """
    if ms is None:
        return ""
    return datetime.fromtimestamp(ms // 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def current_ms() -> int:
    """The sweep clock (ms epoch UTC) — injectable seam for deterministic tests."""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# ── The session-store projection ────────────────────────────────────────────


@dataclass(frozen=True)
class SessionRecord:
    """One row of the opencode ``session`` table, projected to the sweep's needs."""

    id: str
    parent_id: str | None
    title: str
    model: str
    time_created: int
    time_updated: int


@dataclass(frozen=True)
class PartRecord:
    """One row of the opencode ``part`` table, projected to the sweep's needs."""

    id: str
    session_id: str
    time_created: int
    type: str
    data: dict[str, Any]


@dataclass(frozen=True)
class OrphanRecord:
    """One detected orphaned delegation — the dated, flagged ledger event.

    ``orphan_id`` is a stable sha256 of ``parent|subagent`` (mirrors the supervisor flag_id
    pattern) so repeated sweeps de-duplicate; ``detected_at`` is the sweep instant that found
    it; ``idle_minutes`` counts from the subagent's termination (how long the produced-but-
    unreaped result has sat). ``result_available`` is True when the subagent completed (its
    output exists), False when it crashed before finishing.
    """

    orphan_id: str
    detected_at: str
    parent_session_id: str
    parent_title: str
    parent_model: str
    subagent_session_id: str
    subagent_title: str
    subagent_model: str
    spawn_ms: int
    spawn_at: str
    parent_last_step_ms: int | None
    parent_last_step_at: str
    subagent_last_step_ms: int | None
    subagent_last_step_at: str
    terminated_ms: int
    terminated_at: str
    terminated_reason: str  # "completed" | "crashed"
    result_available: bool
    idle_minutes: float
    flagged: bool = True


def orphan_id(parent_session_id: str, subagent_session_id: str) -> str:
    """Stable identity for one delegation, used for ledger de-duplication."""
    return hashlib.sha256(f"{parent_session_id}|{subagent_session_id}".encode()).hexdigest()[:16]


# ── Transcript helpers ──────────────────────────────────────────────────────


def _flat_model(model_json: str | None) -> str:
    """Flatten the native model JSON (``{"providerID":..,"id":..}``) to ``provider/model``."""
    if not model_json:
        return ""
    try:
        parsed = json.loads(model_json)
    except (TypeError, ValueError):
        return ""
    if isinstance(parsed, dict):
        provider = parsed.get("providerID") or ""
        mid = parsed.get("id") or ""
        return f"{provider}/{mid}" if provider and mid else mid
    return str(model_json)


def _task_target(part: PartRecord) -> str | None:
    """The subagent session id a ``task`` tool part delegated to, or ``None``."""
    data = part.data
    if not isinstance(data, dict):
        return None
    if data.get("type") != "tool" or data.get("tool") != "task":
        return None
    state = data.get("state")
    metadata = state.get("metadata") if isinstance(state, dict) else None
    if not isinstance(metadata, dict):
        return None
    return metadata.get("sessionId") or metadata.get("session_id")


def _last_meaningful_step(parts: list[PartRecord], *, after_ms: int | None = None) -> int | None:
    """The latest meaningful-part timestamp; ``after_ms`` restricts to strictly after it."""
    latest: int | None = None
    for part in parts:
        if part.type not in MEANINGFUL_STEP_TYPES:
            continue
        if after_ms is not None and part.time_created <= after_ms:
            continue
        if latest is None or part.time_created > latest:
            latest = part.time_created
    return latest


def _last_step_finish(parts: list[PartRecord]) -> int | None:
    """The latest ``step-finish`` timestamp — the deterministic 'completed' signal."""
    latest: int | None = None
    for part in parts:
        if part.type != "step-finish":
            continue
        if latest is None or part.time_created > latest:
            latest = part.time_created
    return latest


def _task_spawn_ms(parent_parts: list[PartRecord], subagent_session_id: str) -> int | None:
    """The parent-side timestamp of the delegation to ``subagent_session_id``.

    The spawn is the ``task`` tool part whose ``state.metadata.sessionId`` names the
    subagent. Falls back to ``None`` so the caller can use the subagent session's own
    ``time_created``.
    """
    spawns = [p.time_created for p in parent_parts if _task_target(p) == subagent_session_id]
    return min(spawns) if spawns else None


# ── The detection rule (pure, deterministic on transcript timestamps) ───────


def detect_orphans(
    sessions: list[SessionRecord],
    parts: list[PartRecord],
    *,
    now_ms: int | None = None,
    crash_grace_s: int = CRASH_GRACE_S,
) -> list[OrphanRecord]:
    """Return every orphaned delegation in the observed session state.

    Deterministic on the transcript timestamps + ``now_ms``:

    * **parent silent** — no MEANINGFUL part in the parent strictly after the task's spawn
      time (a live parent that is still stepping always fails this arm and is never flagged);
    * **subagent terminated** — a ``step-finish`` exists (``completed``, result produced) OR
      the subagent has been silent for ``crash_grace_s`` with no ``step-finish``
      (``crashed``, no result). A recently-active subagent is still *running* and is never
      flagged.

    Sessions whose parent is not in the observed set are skipped (parent silence cannot be
    verified). Result order is deterministic (sorted by subagent id).
    """
    now_ms = now_ms if now_ms is not None else current_ms()
    if crash_grace_s <= 0:
        raise ValueError("crash_grace_s must be > 0")
    by_session: dict[str, list[PartRecord]] = defaultdict(list)
    for part in parts:
        by_session[part.session_id].append(part)
    # Dedupe by session id: the store projection may hand the SAME session twice when it is
    # both a subagent (of one parent) and a parent (of another) — iterating the raw list
    # would emit a duplicate orphan record for the same (parent, subagent) pair.
    by_id = {s.id: s for s in sessions}

    orphans: list[OrphanRecord] = []
    for subagent in by_id.values():
        if not subagent.parent_id:
            continue
        # A self-referential ``parent_id`` is malformed data (a top-level session's parent is
        # NULL — no session is its own delegation), and without a guard it would be flagged as
        # its own orphan (a spurious ``parent==subagent`` record poisoning the ledger with
        # nonsense). Adversarial p5 probe O3.
        if subagent.parent_id == subagent.id:
            continue
        parent = by_id.get(subagent.parent_id)
        if parent is None:
            continue
        parent_parts = by_session.get(parent.id, [])
        subagent_parts = by_session.get(subagent.id, [])

        spawn_ms = _task_spawn_ms(parent_parts, subagent.id) or subagent.time_created
        # (a) parent silent after spawn — no meaningful step strictly after the spawn.
        parent_last_step = _last_meaningful_step(parent_parts, after_ms=spawn_ms)
        if parent_last_step is not None:
            continue
        # (b) subagent terminated.
        finish_ms = _last_step_finish(subagent_parts)
        if finish_ms is not None:
            terminated_ms = finish_ms
            reason = "completed"
            result_available = True
        else:
            subagent_last = _last_meaningful_step(subagent_parts)
            last_activity = subagent_last if subagent_last is not None else subagent.time_updated
            if now_ms - last_activity <= crash_grace_s * 1000:
                continue  # no step-finish but recently active → still running
            terminated_ms = last_activity
            reason = "crashed"
            result_available = False

        subagent_last = _last_meaningful_step(subagent_parts)
        idle_minutes = (now_ms - terminated_ms) / 60000.0
        orphans.append(
            OrphanRecord(
                orphan_id=orphan_id(parent.id, subagent.id),
                detected_at=utc_now(),
                parent_session_id=parent.id,
                parent_title=parent.title,
                parent_model=parent.model,
                subagent_session_id=subagent.id,
                subagent_title=subagent.title,
                subagent_model=subagent.model,
                spawn_ms=spawn_ms,
                spawn_at=_iso_from_ms(spawn_ms),
                parent_last_step_ms=parent_last_step,
                parent_last_step_at=_iso_from_ms(parent_last_step),
                subagent_last_step_ms=subagent_last,
                subagent_last_step_at=_iso_from_ms(subagent_last),
                terminated_ms=terminated_ms,
                terminated_at=_iso_from_ms(terminated_ms),
                terminated_reason=reason,
                result_available=result_available,
                idle_minutes=round(idle_minutes, 2),
            )
        )
    orphans.sort(key=lambda o: (o.subagent_session_id, o.parent_session_id))
    return orphans


# ── Session store (read-only) ───────────────────────────────────────────────


class SQLiteSessionStore:
    """Read the opencode server's session store **read-only** (the sweep never writes it).

    Only the subagent sessions (``parent_id`` set) and their parents are loaded, with the
    parts of exactly those sessions — bounded, not a full-database read.
    """

    _SESSION_COLS = ("id", "parent_id", "title", "model", "time_created", "time_updated")

    def __init__(self, db_path: str | Path) -> None:
        uri = f"file:{Path(db_path).resolve()}?mode=ro"
        self._conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self._conn.close()

    def load(self) -> tuple[list[SessionRecord], list[PartRecord]]:
        sessions = self._load_sessions()
        ids = {s.id for s in sessions}
        ids.update(s.parent_id for s in sessions if s.parent_id)
        parts = self._load_parts(ids)
        return sessions, parts

    def _load_sessions(self) -> list[SessionRecord]:
        query = (
            "SELECT id,parent_id,title,model,time_created,time_updated FROM session "
            "WHERE parent_id IS NOT NULL AND parent_id != ''"
        )
        subagents = [self._to_session(row) for row in self._conn.execute(query)]
        parent_ids = {s.parent_id for s in subagents if s.parent_id}
        parents: list[SessionRecord] = []
        if parent_ids:
            placeholders = ",".join("?" for _ in parent_ids)
            query = (
                "SELECT id,parent_id,title,model,time_created,time_updated FROM session "
                f"WHERE id IN ({placeholders})"
            )
            parents = [self._to_session(row) for row in self._conn.execute(query, tuple(parent_ids))]
        return subagents + parents

    def _load_parts(self, session_ids: set[str]) -> list[PartRecord]:
        parts: list[PartRecord] = []
        for sid in session_ids:
            for row in self._conn.execute(
                "SELECT id,session_id,time_created,data FROM part WHERE session_id=?", (sid,)
            ):
                try:
                    data = json.loads(row["data"])
                except (TypeError, ValueError):
                    data = {}
                if not isinstance(data, dict):
                    data = {}
                parts.append(
                    PartRecord(
                        id=row["id"],
                        session_id=row["session_id"],
                        time_created=row["time_created"],
                        type=data.get("type", ""),
                        data=data,
                    )
                )
        return parts

    @staticmethod
    def _to_session(row: sqlite3.Row) -> SessionRecord:
        return SessionRecord(
            id=row["id"],
            parent_id=row["parent_id"],
            title=row["title"],
            model=_flat_model(row["model"]),
            time_created=row["time_created"],
            time_updated=row["time_updated"],
        )


# ── Zombie reaping (best-effort; NOT steering) ──────────────────────────────


def _proc_table() -> dict[int, str]:
    """pid → cmdline for every visible process (Linux ``/proc``), best-effort."""
    table: dict[int, str] = {}
    try:
        entries = os.listdir("/proc")
    except OSError:
        return table
    for entry in entries:
        if not entry.isdigit():
            continue
        pid = int(entry)
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as handle:
                raw = handle.read().decode(errors="replace")
        except OSError:
            continue
        table[pid] = raw.replace("\x00", " ")
    return table


def reap_orphaned_subagents(
    orphans: list[OrphanRecord],
    *,
    process_table: dict[int, str] | None = None,
) -> dict[str, list[int]]:
    """SIGTERM any still-alive process whose cmdline references an orphaned subagent.

    Zombie reaping only — the subagent has already terminated (completed or crashed) per the
    detection rule, so a matching process is a leaked OS-level child, not a working agent.
    This is the one allowed "actuation" and it is *not* steering: it never touches the parent
    campaign or the opencode server's session state. ``process_table`` is injectable so tests
    verify the reap without touching real processes. Returns ``{subagent_id: [pids]}``.
    """
    if not orphans:
        return {}
    table = process_table if process_table is not None else _proc_table()
    reaped: dict[str, list[int]] = {}
    for orphan in orphans:
        pids = [
            pid for pid, cmdline in table.items() if orphan.subagent_session_id in cmdline
        ]
        if not pids:
            continue
        for pid in pids:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(pid, signal.SIGTERM)
        reaped[orphan.subagent_session_id] = pids
    return reaped


# ── Ledger + surfacing (durable JSONL first, then the bounded Redis hot path) ─


def load_recorded_orphan_ids(ledger_path: str | Path) -> set[str]:
    """The ``orphan_id``s already on the ledger, so a repeated sweep never re-records."""
    recorded: set[str] = set()
    try:
        lines = Path(ledger_path).read_text().splitlines()
    except FileNotFoundError:
        return recorded
    for line in lines:
        try:
            decoded = json.loads(line)
        except (TypeError, json.JSONDecodeError):
            continue
        oid = decoded.get("orphan_id")
        if isinstance(oid, str) and oid:
            recorded.add(oid)
    return recorded


def record_orphan(
    orphan: OrphanRecord,
    *,
    ledger_path: str | Path,
    redis_client: Any = None,
) -> None:
    """Persist one dated, flagged orphan record durably, then the Redis hot path.

    Order mirrors ``scripts/supervise.py:emit_flag``: the append-only JSONL write comes
    first (a Redis outage cannot erase the event), the bounded hot list second, and the
    canonical-state registration (``FINOPS_KB_WRITE``-gated, best-effort) last — a downed
    DB2 knowledge stream must never cost the durable write.
    """
    payload = canonical_json(asdict(orphan))
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(payload + "\n")
    if redis_client is not None:
        try:
            redis_client.lpush(ORPHAN_EVENTS_KEY, payload)
            redis_client.ltrim(ORPHAN_EVENTS_KEY, 0, ORPHAN_EVENTS_MAX - 1)
        except Exception:  # noqa: BLE001 — the durable write already succeeded
            pass
    if os.environ.get("FINOPS_KB_WRITE") == "1":
        try:
            from agentic_dynamics.control.orphan_ingestion import derive_orphan_record
            from agentic_dynamics.knowledge import knowledge_stream as ks
            from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID

            ks.register_records(
                [derive_orphan_record(asdict(orphan), repository_id=REPOSITORY_ID)],
                fail_loud=False,
            )
        except Exception:  # noqa: BLE001 — best-effort; the ledger write already landed
            pass


# ── The one-pass sweep driver (used by scripts/orphan_sweep.py and the Control Room) ─


def sweep_once(
    store: SQLiteSessionStore,
    *,
    ledger_path: str | Path,
    redis_client: Any = None,
    now_ms: int | None = None,
    crash_grace_s: int = CRASH_GRACE_S,
    process_table: dict[int, str] | None = None,
) -> list[OrphanRecord]:
    """One full sweep cycle: observe → detect → reap → record → surface (flag-only).

    Returns the newly-recorded orphans. Orphans already on the ledger are observed but not
    re-recorded (de-duplicated by ``orphan_id``). Never restarts/retries/resumes/steers.
    """
    sessions, parts = store.load()
    orphans = detect_orphans(sessions, parts, now_ms=now_ms, crash_grace_s=crash_grace_s)
    recorded = load_recorded_orphan_ids(ledger_path)
    surfaced: list[OrphanRecord] = []
    for orphan in orphans:
        if orphan.orphan_id in recorded:
            continue
        reap_orphaned_subagents([orphan], process_table=process_table)
        record_orphan(orphan, ledger_path=ledger_path, redis_client=redis_client)
        surfaced.append(orphan)
        recorded.add(orphan.orphan_id)
    return surfaced
