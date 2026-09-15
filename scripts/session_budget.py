#!/usr/bin/env python3
"""session_budget.py — the AIO's session budget check (capacity-derived, 2026-09-15 policy).

The 25-hour 2026-09-13 session ran to ~698K context tokens with zero compactions. The first
repair (decision f987cde9) made the failure class executable against a FIXED policy budget
(200K tokens / 80 assistant turns). The operator's 2026-09-15 context-policy change replaced
that constant with the ACTIVE session model's resolved capacity:

    agentic-dynamics session budget                        # human verdict
    agentic-dynamics session budget --json                 # machine surface: session-budget/v2

Judgment (context = the installed runtime's own overflow measure on the LAST COMPLETED
assistant usage sample — ``tokens.total``, else ``input + output + cache read + cache write``;
turns = assistant messages so far, TELEMETRY ONLY — message count is never a stopping
condition):

* ``OK``      — below the advisory fraction of the effective limit: keep working.
* ``WARN``    — at/above 80% of the effective limit: ADVISORY. Informational; not a stopping
  condition; never a reason to refuse new work.
* ``COMPACT`` — at/above the effective (usable) boundary: the installed runtime compacts
  natively on the next request and the SAME session/task continues. Do not close; re-evaluate
  against the reduced context afterward. (When the runtime's native compaction is disabled,
  no mechanism can reduce the context and the verdict is CLOSE instead.)
* ``CLOSE``   — at/over the model's HARD context limit: the next request cannot be processed;
  close and hand off to a fresh session.
* ``UNJUDGED`` — the session/model/capacity cannot be measured. Exit code 1, deliberately: an
  unknown budget is never treated as unlimited (the same rule as unknown cost) — and never as
  a fabricated OK.

Capacity is resolved by ``agentic_dynamics.core.session_capacity`` — the ported
opencode-1.18.15 calculation (the runtime's own ``maxOutputTokens``/compaction-reserve
formula), fed by the ACTIVE model recorded on the session row (the repository default and any
child workflow model are deliberately ignored), the installed catalog cache, and the runtime
config overlays. That module is shared by this CLI, the capsule (``session_open.py``), and the
fleet exec-boundary gate (``scripts/fleet/spawn_wrapper.py``), so all three return the SAME
resolution and judgment. The explicit operator override ``FINOPS_SESSION_CTX_LIMIT`` is read
by the same module, so an override is consistent across all three surfaces.

Identity (unchanged): the session under judgment is the EXPLICIT one — ``--session-id``, else
``FINOPS_SESSION_ID``. There is NO most-recently-updated fallback; an absent identity and a
nonexistent id are both UNJUDGED (exit 1) with a reason.

Measurement (the zero-overwrite fix, unchanged): an unfinished assistant message (no tokens
block, or the pending all-zero shape) must never overwrite a valid reading with zero — the
reading falls back to the most recent COMPLETED sample and carries ``usage_incomplete: true``.

Exit codes: 0 = OK, 1 = WARN (advisory) / UNJUDGED, 2 = COMPACT (native compaction expected;
re-evaluate after), 3 = CLOSE (close now). Every judgment appends one line to the session-budget
journal (append-only; override the path with ``FINOPS_SESSION_BUDGET_JOURNAL`` for tests).

The verdict is derived from the opencode session database (``~/.local/share/opencode/opencode.db``
by default; ``FINOPS_OPENCODE_DB`` overrides).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
from pathlib import Path

try:
    import _bootstrap  # noqa: F401
except ImportError:
    from scripts import _bootstrap  # noqa: F401

from agentic_dynamics.core import session_capacity as sc

SCHEMA_ID = "session-budget/v2"

#: The explicit-session environment (the runtime's AIO session identity).
SESSION_ID_ENV = "FINOPS_SESSION_ID"

#: The journal each judgment appends to (append-only; a budget observation is never rewritten).
JOURNAL_DEFAULT = (
    Path(__file__).resolve().parent.parent
    / "experiments" / "results" / "control" / "session_budget.jsonl"
)

#: Exit codes — COMPACT and CLOSE are DISTINCT on purpose: collapsing them would let an
#: automation close a session the runtime is about to compact.
EXIT_CODES = {"OK": 0, "WARN": 1, "UNJUDGED": 1, "COMPACT": 2, "CLOSE": 3}


def _default_db() -> Path:
    return Path(os.environ.get("FINOPS_OPENCODE_DB") or Path.home() / ".local/share/opencode/opencode.db")


def _resolve_session_id(args_session: str | None, env: dict | None = None) -> str | None:
    """The EXPLICIT session identity: the flag, then the runtime env. ``None`` = not supplied
    (a refusal to guess — never "pick the most recently updated row")."""
    source = os.environ if env is None else env
    return (args_session or source.get(SESSION_ID_ENV) or "").strip() or None


def _session_exists(db_path: Path, session_id: str) -> bool:
    """True when the named session row exists (a nonexistent id is a refusal, not a fallback)."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        cur.execute("SELECT 1 FROM session WHERE id=?", (session_id,))
        return cur.fetchone() is not None
    finally:
        con.close()


def _measure(db_path: Path, session_id: str) -> tuple[int, int, bool]:
    """``(turns, context, usage_incomplete)`` for the session.

    ``context`` — the installed runtime's overflow measure on the LAST COMPLETED assistant
    usage sample (``tokens.total``, else ``input + output + cache read + cache write``). A
    sample is COMPLETED only when it carries a NON-ZERO value: OpenCode initializes a pending
    message's usage fields to ZERO before the turn finalizes, so keys-present-but-all-zero is
    the real pending shape — treating it as completed is exactly the zero-overwrite bug (Astra
    finding, 2026-09-14: a 240,000 reading followed by a pending zero-valued message measured
    0/OK). Both shapes — absent fields and all-zero fields — leave the reading untouched and
    set ``usage_incomplete``. A session with no completed sample reads (0, 0, True) — an
    honest "nothing measurable", flagged, never a silent zero.
    """
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT data FROM message WHERE session_id=? ORDER BY time_created",
            (session_id,),
        )
        turns = 0
        context = 0
        usage_incomplete = False
        for (blob,) in cur.fetchall():
            try:
                data = json.loads(blob)
            except (json.JSONDecodeError, TypeError):
                continue
            if data.get("role") != "assistant":
                continue
            turns += 1
            measured = sc.usage_context_tokens(data.get("tokens"))
            if measured is None:
                usage_incomplete = True
                continue
            context = measured
        return turns, context, usage_incomplete
    finally:
        con.close()


def _resolve(
    session_id: str, *, db_path: Path, env: dict | None = None
) -> dict:
    """One shared resolution for the CLI and the gate: measurement + capacity, no verdict yet.

    ``status`` is one of ``"measured"`` (context + capacity available), ``"initial"`` (no
    assistant message yet — the named exception), ``"unmeasured"`` (a session whose every
    sample is pending), or ``"unresolved"`` (identity/capacity gaps). The caller decides the
    verdict shape, so the CLI and the gate can never disagree about WHAT was measured.
    """
    source = os.environ if env is None else env
    result: dict = {
        "status": "unresolved",
        "session_id": session_id,
        "turns": 0,
        "context_tokens": 0,
        "usage_incomplete": False,
        "capacity": None,
        "model": None,
        "reason": "",
    }
    path = Path(db_path)
    if not path.is_file():
        result["reason"] = f"session db {path} not found"
        return result
    sid = (session_id or "").strip()
    if not sid:
        result["reason"] = f"no session identity supplied (--session-id or {SESSION_ID_ENV})"
        return result
    if not _session_exists(path, sid):
        result["reason"] = f"session {sid!r} does not exist in {path}"
        return result
    try:
        turns, context, incomplete = _measure(path, sid)
    except Exception as exc:  # noqa: BLE001 — an unreadable measurement is never OK
        result["reason"] = f"{type(exc).__name__}: {exc}"
        return result
    result.update({"turns": turns, "context_tokens": context, "usage_incomplete": bool(incomplete)})
    if turns == 0:
        result["status"] = "initial"
        result["reason"] = "initial session: no usage recorded yet"
        return result
    if incomplete and context == 0:
        result["status"] = "unmeasured"
        result["reason"] = "no usable measurement: every recorded usage sample is pending/incomplete"
        return result
    capacity, capacity_reason, model = sc.resolve_capacity(path, sid, env=source)
    if model is not None:
        result["model"] = {
            "provider_id": model.provider_id,
            "model_id": model.model_id,
            "variant": model.variant,
            "source": model.source,
        }
    if capacity is None:
        result["reason"] = capacity_reason
        return result
    result["status"] = "measured"
    result["capacity"] = capacity
    return result


def _verdict_for(resolved: dict) -> tuple[str, str, dict]:
    """Map a resolution to ``(verdict, reason, capacity_block)`` — ONE judgment, shared."""
    status = resolved.get("status")
    if status == "initial":
        return "OK", str(resolved.get("reason") or ""), {}
    if status == "unmeasured":
        return "UNJUDGED", str(resolved.get("reason") or ""), {}
    if status != "measured":
        return "UNJUDGED", str(resolved.get("reason") or "capacity unresolved"), {}
    capacity = resolved["capacity"]
    context = int(resolved["context_tokens"])
    verdict = sc.classify(context, capacity)
    reason = ""
    if verdict == "WARN":
        reason = (
            f"advisory: context {context:,} >= {capacity.warn_fraction:.0%} of effective limit "
            f"{capacity.effective_limit:,} — informational, not a stopping condition"
        )
    elif verdict == "COMPACT":
        reason = (
            f"at the native compaction boundary: context {context:,} >= effective limit "
            f"{capacity.effective_limit:,} (hard {capacity.hard_limit:,}) — the installed "
            f"runtime compacts natively on the next request and this session continues; "
            f"re-evaluate against the reduced context"
        )
    elif verdict == "CLOSE" and not capacity.compaction_enabled:
        reason = (
            f"context {context:,} >= effective limit {capacity.effective_limit:,} and native "
            f"compaction is disabled (compaction.auto=false) — no mechanism reduces the "
            f"context; close and hand off"
        )
    elif verdict == "CLOSE":
        reason = (
            f"context {context:,} >= the model's hard context limit {capacity.hard_limit:,} — "
            f"the next request cannot be processed; close and hand off to a fresh session"
        )
    if resolved.get("usage_incomplete"):
        suffix = "usage incomplete — last completed sample used"
        reason = f"{reason}; {suffix}" if reason else suffix
    return verdict, reason, capacity.as_dict()


def measure_verdict(
    session_id: str | None,
    *,
    db_path: Path | None = None,
    env: dict | None = None,
) -> tuple[str, str, bool]:
    """The measurement seam for programmatic callers (the AIO exec-boundary gate).

    Returns ``(verdict, reason, backend_available)``:

    * ``backend_available=False`` — the session DATABASE is not present at this location
      (the containerized gate has no host DB mounted). The caller must NOT read this as a
      verdict: a gate that cannot measure defers, and the host-side gate (the broker) —
      which owns the canonical database — measures before the launch effect.
    * a genuinely INITIAL session (no assistant message recorded yet) is ``OK`` with the
      explicit reason ``"initial session: no usage recorded yet"`` — the one defined
      exception, named rather than silently zero.
    * a session whose every recorded usage sample is pending/incomplete has NO usable
      measurement: ``UNJUDGED`` with a named reason — never a silent 0/OK.
    * a session whose active model or capacity cannot be resolved is ``UNJUDGED`` — never a
      fabricated capacity, never OK.
    * otherwise the shared capacity judgment.

    The judged session is the EXPLICIT identity; there is no most-recently-updated fallback.
    """
    try:
        path = Path(db_path) if db_path else _default_db()
        if not path.is_file():
            return "UNJUDGED", f"session db {path} not found", False
        sid = (session_id or "").strip()
        if not sid:
            return "UNJUDGED", f"no session identity supplied (--session-id or {SESSION_ID_ENV})", True
        resolved = _resolve(sid, db_path=path, env=env)
        verdict, reason, _ = _verdict_for(resolved)
        return verdict, reason, True
    except Exception as exc:  # noqa: BLE001 — an unreadable budget is UNJUDGED, never OK
        return "UNJUDGED", f"{type(exc).__name__}: {exc}", True


def _append_journal(entry: dict[str, object]) -> None:
    path = Path(os.environ.get("FINOPS_SESSION_BUDGET_JOURNAL") or JOURNAL_DEFAULT)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics session budget",
        description="Judge the AIO's session context against the ACTIVE model's resolved "
        "capacity: OK / WARN (advisory) / COMPACT (native compaction; re-evaluate) / CLOSE "
        "(session-budget/v2).",
    )
    parser.add_argument("--db", default=None, help=f"opencode session db (default: {_default_db()})")
    parser.add_argument("--session-id", default=None,
                        help="the session id to judge (default: $FINOPS_SESSION_ID — the "
                             "runtime's AIO session identity; there is NO most-recently-updated "
                             "fallback: an absent or nonexistent id is UNJUDGED)")
    parser.add_argument("--json", action="store_true", help="emit session-budget/v2 JSON")
    parser.add_argument("--no-journal", action="store_true", help="skip the journal append")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db_path = Path(args.db) if args.db else _default_db()

    session_id = _resolve_session_id(args.session_id) or ""
    if db_path.is_file() and session_id:
        resolved = _resolve(session_id, db_path=db_path)
    else:
        resolved = {"status": "unresolved", "session_id": session_id,
                    "reason": f"session db {db_path} not found" if not db_path.is_file()
                    else f"no session identity supplied — pass --session-id or export {SESSION_ID_ENV}",
                    "turns": 0, "context_tokens": 0, "usage_incomplete": False,
                    "capacity": None, "model": None}
    verdict, reason, capacity_block = _verdict_for(resolved)
    capacity_obj = resolved.get("capacity")
    capacity_valid = capacity_obj is not None

    now = sc.utc_now()
    result: dict = {
        "schema": SCHEMA_ID,
        "ts": now,
        "session_id": session_id,
        "turns": int(resolved.get("turns") or 0),
        "context_tokens": int(resolved.get("context_tokens") or 0),
        "usage_incomplete": bool(resolved.get("usage_incomplete")) and verdict != "UNJUDGED",
        "verdict": verdict,
        "reason": reason,
        "model": resolved.get("model"),
        "capacity": capacity_block or None,
        "remaining_tokens": (
            max(0, capacity_obj.effective_limit - int(resolved["context_tokens"]))
            if capacity_valid else None
        ),
        "provenance": capacity_obj.provenance if capacity_valid else {},
    }
    if not args.no_journal:
        # The verdict must render even when the journal cannot.
        with contextlib.suppress(OSError):
            _append_journal(result)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(_render_human(result))
    return EXIT_CODES.get(verdict, 1)


def _render_human(result: dict) -> str:
    capacity = result.get("capacity") or {}
    model = result.get("model") or {}
    identity = (
        f"{model.get('provider_id')}/{model.get('model_id')}" if model.get("provider_id") else "model unresolved"
    )
    if capacity.get("effective_limit"):
        budget = (
            f"context {result['context_tokens']:,}/{capacity['effective_limit']:,} "
            f"(hard {capacity['hard_limit']:,}; response headroom "
            f"{capacity['response_headroom_tokens']:,}; compaction reserve "
            f"{capacity['compaction_reserved_tokens']:,})"
        )
    else:
        budget = f"context {result['context_tokens']:,} (capacity unresolved)"
    line = (
        f"session budget: {result['verdict']} — {identity} · {budget} · "
        f"turns {result['turns']} (telemetry)"
    )
    if result.get("remaining_tokens") is not None:
        line += f" · remaining {result['remaining_tokens']:,}"
    if result.get("reason"):
        line += f" — {result['reason']}"
    return line


if __name__ == "__main__":
    raise SystemExit(main())
