#!/usr/bin/env python3
"""session_budget.py — the AIO's session budget check (capacity-derived; ADVISORY since 2026-09-16).

The 25-hour 2026-09-13 session ran to ~698K context tokens with zero compactions. The first
repair (decision f987cde9) made the failure class executable against a FIXED policy budget
(200K tokens / 80 assistant turns). The operator's 2026-09-15 context-policy change replaced
that constant with the ACTIVE session model's resolved capacity. The operator's 2026-09-16
delivery-path simplification then separated this DIAGNOSTIC from workflow ADMISSION: the
verdict informs the coordinator's own wrap-up/hand-off discipline and is reported wherever
it is consumed; it never blocks a valid submission. Native identity, the durable binding,
project association, source/scope guarantees, and FINANCIAL admission remain the refusals —
a missing chat token measurement is not a missing authorization.

    agentic-dynamics session budget                        # human verdict
    agentic-dynamics session budget --json                 # machine surface: session-budget/v2

Judgment (context = the installed runtime's OWN overflow measure on the LAST COMPLETED
assistant usage sample — ``tokens.total``, else ``input + output + cache read + cache write``;
``reasoning`` is NOT in the sum, matching the runtime exactly; turns = assistant messages so
far, TELEMETRY ONLY — message count is never a stopping condition):

* ``OK``      — below the advisory fraction of the operative limit: keep working. Also the
  named POST-COMPACTION state: when the last assistant message is a completed compaction
  summary, the runtime skips its overflow check and continues from the compacted context —
  the pre-compaction reading is stale and must not block the first resumed work; the check
  mirrors the runtime and re-measures with the next completed sample.
* ``WARN``    — at/above 80% of the operative limit: ADVISORY. Informational; not a stopping
  condition; never a reason to refuse new work.
* ``COMPACT`` — at/above the NATIVE usable boundary: the runtime's own compaction may engage
  on its next request, and the SAME session/task continues. This check REPORTS the boundary;
  it does not trigger, prove, or record compaction (only the runtime does that, at its native
  boundary). Do not close; re-evaluate against the reduced context afterward. (When the
  runtime's native compaction is disabled, no mechanism can reduce the context and the
  verdict is CLOSE instead.)
* ``CLOSE``   — at/over the model's HARD context limit (the next request cannot be processed),
  or at/over a LOCAL POLICY cap below the native boundary (``FINOPS_SESSION_CTX_LIMIT`` —
  a policy cap is not a native trigger, so nothing will reduce the context; close and hand
  off).
* ``UNJUDGED`` — the session/model/capacity cannot be measured. Exit code 1, deliberately: it
  is reported as an unavailable ADVISORY with its reason — never a fabricated OK, and never a
  fabricated refusal (workflow admission no longer consumes this verdict; see the 2026-09-16
  policy above).

Capacity is resolved by ``agentic_dynamics.core.session_capacity``: the installed runtime's
own CLI resolution first (``opencode models --verbose``), the catalog+config fallback second —
the same resolution the capsule (``session_open.py``) and the fleet exec-boundary's advisory
report (``scripts/fleet/spawn_wrapper.py:aio_capacity_report``) consume, so all of them return
the SAME judgment. The operator override ``FINOPS_SESSION_CTX_LIMIT`` is a clamped LOCAL POLICY
cap read by the same resolver.

Identity (unchanged): the session under judgment is the EXPLICIT one — ``--session-id``, else
``FINOPS_SESSION_ID``. There is NO most-recently-updated fallback; an absent identity and a
nonexistent id are both UNJUDGED (exit 1) with a reason.

Measurement (the zero-overwrite fix, unchanged): an unfinished assistant message (no tokens
block, or the pending all-zero shape) must never overwrite a valid reading with zero — the
reading falls back to the most recent COMPLETED sample and carries ``usage_incomplete: true``.
A completed COMPACTION SUMMARY is never a context sample (its usage describes the summary
generation call over the old conversation, not the new context); it marks the post-compaction
state instead.

Exit codes: 0 = OK, 1 = WARN (advisory) / UNJUDGED, 2 = COMPACT (at/above the native boundary;
re-evaluate after), 3 = CLOSE (close now). Every judgment appends one line to the session-budget
journal (append-only; override the path with ``FINOPS_SESSION_BUDGET_JOURNAL`` for tests).

Programmatic callers use ``measure_report`` for the structured judgment
(``{verdict, reason, backend_available, measured}``): ``backend_available`` says the session
database was reachable; ``measured`` says a CURRENT usable reading produced the verdict — a
corrupt database reports ``backend_available=True`` with ``measured=False``, never a claimed
measurement. ``measure_verdict`` keeps the 3-tuple shape for existing callers, where the third
element is backend availability (NOT a measurement).

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


def _measure(db_path: Path, session_id: str) -> tuple[int, int, bool, bool]:
    """``(turns, context, usage_incomplete, post_compaction)`` for the session.

    ``context`` — the installed runtime's overflow measure on the LAST COMPLETED non-summary
    assistant usage sample (``tokens.total``, else ``input + output + cache read + cache
    write``; ``reasoning`` excluded, matching the runtime). A sample is COMPLETED only when it
    carries a NON-ZERO value: OpenCode initializes a pending message's usage fields to ZERO
    before the turn finalizes, so keys-present-but-all-zero is the real pending shape —
    treating it as completed is exactly the zero-overwrite bug (Astra finding, 2026-09-14).
    Both shapes — absent fields and all-zero fields — leave the reading untouched and set
    ``usage_incomplete``.

    ``post_compaction`` — the LAST assistant message is a COMPLETED compaction summary
    (``summary: true`` plus non-zero usage or a finish; the runtime's pairing marks:
    ``summary && finish && !error``). The runtime SKIPS its overflow check for that message
    (its run loop guards ``he.summary !== true``) and continues from the compacted context;
    the summary's own usage describes the summary GENERATION call over the old conversation,
    so it must never be read as the new context — and the stale pre-compaction reading must
    not resurrect and block the first resumed turn (reviewer reproduction, 2026-09-15). A
    completed non-summary sample CLEARS the state; a pending turn does not.
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
        compaction_done = False
        for (blob,) in cur.fetchall():
            try:
                data = json.loads(blob)
            except (json.JSONDecodeError, TypeError):
                continue
            if data.get("role") != "assistant":
                continue
            turns += 1
            measured = sc.usage_context_tokens(data.get("tokens"))
            if data.get("summary") is True:
                # A compaction summary is NEVER a context sample. Completed (non-zero usage
                # or a finish) marks the post-compaction boundary; the pending all-zero shape
                # (opencode creates it that way, then fills it) marks the in-flight boundary.
                if measured is not None or data.get("finish"):
                    compaction_done = True
                else:
                    usage_incomplete = True
                continue
            if measured is None:
                usage_incomplete = True
                continue  # a pending turn never clears the post-compaction state
            context = measured
            compaction_done = False  # a fresh completed sample is the current context
        return turns, context, usage_incomplete, compaction_done
    finally:
        con.close()


def _resolve(
    session_id: str, *, db_path: Path, env: dict | None = None
) -> dict:
    """One shared resolution for the CLI and the gate: measurement + capacity, no verdict yet.

    ``status`` is one of ``"measured"`` (context + capacity available), ``"initial"`` (no
    assistant message yet — the named exception), ``"unmeasured"`` (a session whose every
    sample is pending), or ``"unresolved"`` (identity/capacity gaps, INCLUDING an unreadable
    database — the whole body is inside the shared error boundary, so a corrupt database
    yields a structured UNJUDGED, never a crash: reviewer finding 2026-09-15).
    """
    source = os.environ if env is None else env
    result: dict = {
        "status": "unresolved",
        "session_id": session_id,
        "turns": 0,
        "context_tokens": 0,
        "usage_incomplete": False,
        "post_compaction": False,
        "capacity": None,
        "model": None,
        "reason": "",
        #: Whether the session DATABASE was reachable to read (the file existed). Distinct
        #: from a usable measurement: a corrupt database or a pending-only session reaches
        #: the backend and still measures nothing.
        "backend_available": False,
    }
    try:
        path = Path(db_path)
        if not path.is_file():
            result["reason"] = f"session db {path} not found"
            return result
        result["backend_available"] = True
        sid = (session_id or "").strip()
        if not sid:
            result["reason"] = f"no session identity supplied (--session-id or {SESSION_ID_ENV})"
            return result
        if not _session_exists(path, sid):
            result["reason"] = f"session {sid!r} does not exist in {path}"
            return result
        turns, context, incomplete, post_compaction = _measure(path, sid)
        result.update({
            "turns": turns,
            "context_tokens": context,
            "usage_incomplete": bool(incomplete),
            "post_compaction": bool(post_compaction),
        })
        if turns == 0:
            result["status"] = "initial"
            result["reason"] = "initial session: no usage recorded yet"
            return result
        if incomplete and context == 0 and not post_compaction:
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
    except Exception as exc:  # noqa: BLE001 — an unreadable budget is UNJUDGED, never OK
        result["status"] = "unresolved"
        result["reason"] = f"{type(exc).__name__}: {exc}"
        return result


def _verdict_for(resolved: dict) -> tuple[str, str, dict]:
    """Map a resolution to ``(verdict, reason, capacity_block)`` — ONE judgment, shared."""
    status = resolved.get("status")
    if status == "initial":
        return "OK", str(resolved.get("reason") or ""), {}
    if status != "measured":
        return "UNJUDGED", str(resolved.get("reason") or "capacity unresolved"), {}
    capacity = resolved["capacity"]
    if resolved.get("post_compaction"):
        # Mirrors the runtime: the overflow check is skipped for a completed compaction
        # summary; the session continues from the replaced context and re-measures.
        return (
            "OK",
            "post-compaction: the completed compaction summary replaced the native context; "
            "the runtime skips its overflow check for the summary and the session continues — "
            "the pre-compaction reading is not the current context; measurement resumes with "
            "the next completed sample",
            capacity.as_dict(),
        )
    context = int(resolved["context_tokens"])
    verdict = sc.classify(context, capacity)
    reason = ""
    if verdict == "WARN":
        reason = (
            f"advisory: context {context:,} >= {capacity.warn_fraction:.0%} of the operative "
            f"limit {capacity.effective_limit:,} — informational, not a stopping condition"
        )
    elif verdict == "COMPACT":
        reason = (
            f"at the native compaction boundary: context {context:,} >= native usable "
            f"{capacity.native_effective_limit:,} (hard {capacity.hard_limit:,}) — the "
            f"installed runtime compacts natively on the next request and this session "
            f"continues; re-evaluate against the reduced context"
        )
    elif verdict == "CLOSE":
        if context >= capacity.hard_limit:
            reason = (
                f"context {context:,} >= the model's hard context limit "
                f"{capacity.hard_limit:,} — the next request cannot be processed; close and "
                f"hand off to a fresh session"
            )
        elif not capacity.compaction_enabled:
            reason = (
                f"context {context:,} >= native usable {capacity.native_effective_limit:,} and "
                f"native compaction is disabled (compaction.auto=false) — no mechanism reduces "
                f"the context; close and hand off"
            )
        else:
            reason = (
                f"context {context:,} >= the LOCAL POLICY limit "
                f"{capacity.policy_limit:,} ({sc.EFFECTIVE_LIMIT_ENV}; native compaction "
                f"starts at {capacity.native_effective_limit:,}) — a policy limit is not a "
                f"native trigger, so nothing reduces the context there; close and hand off"
            )
    if resolved.get("usage_incomplete") and not resolved.get("post_compaction"):
        suffix = "usage incomplete — last completed sample used"
        reason = f"{reason}; {suffix}" if reason else suffix
    return verdict, reason, capacity.as_dict()


def _measured(resolved: dict) -> bool:
    """Whether the verdict rests on a CURRENT usable reading — not merely a reachable backend.

    False for every named non-measurement, even when the database was read: the initial
    session (no usage recorded yet), an every-sample-pending session (no usable sample), a
    completed compaction summary (the retained reading is stale BY CONSTRUCTION — measurement
    resumes with the next completed sample), an unresolvable identity/capacity, and any
    unreadable database (the shared error boundary lands in ``unresolved``).
    """
    return bool(resolved.get("status") == "measured" and not resolved.get("post_compaction"))


def measure_report(
    session_id: str | None,
    *,
    db_path: Path | None = None,
    env: dict | None = None,
) -> dict:
    """The structured measurement report: ``{verdict, reason, backend_available, measured}``.

    ``backend_available`` — the session DATABASE was reachable (present at this location).
    ``measured`` — the verdict rests on a CURRENT usable reading (see :func:`_measured`).
    The two are deliberately distinct: a corrupt database yields
    ``UNJUDGED / backend_available=True / measured=False`` (never a claimed measurement), a
    containerized gate with no host DB mounted yields ``False / False``, and a pending-only
    session yields ``True / False``. Callers report both; no consumer converts an absent
    measurement into a refusal (2026-09-16 policy — a missing chat token measurement is not
    a missing authorization).
    """
    try:
        path = Path(db_path) if db_path else _default_db()
        resolved = _resolve(session_id or "", db_path=path, env=env)
        verdict, reason, _ = _verdict_for(resolved)
        return {
            "verdict": verdict,
            "reason": reason,
            "backend_available": bool(resolved.get("backend_available")),
            "measured": _measured(resolved),
        }
    except Exception as exc:  # noqa: BLE001 — an unreadable budget is UNJUDGED, never OK
        return {
            "verdict": "UNJUDGED",
            "reason": f"{type(exc).__name__}: {exc}",
            "backend_available": False,
            "measured": False,
        }


def measure_verdict(
    session_id: str | None,
    *,
    db_path: Path | None = None,
    env: dict | None = None,
) -> tuple[str, str, bool]:
    """The 3-tuple measurement seam: ``(verdict, reason, backend_available)``.

    The third element is BACKEND AVAILABILITY, not a usable measurement — a corrupt database
    reports it True while measuring nothing. Callers that report the distinction (the
    exec-boundary advisory) use :func:`measure_report`. Semantics of the verdicts:

    * a genuinely INITIAL session (no assistant message recorded yet) is ``OK`` with the
      explicit reason ``"initial session: no usage recorded yet"`` — the one defined
      exception, named rather than silently zero.
    * a session whose every recorded usage sample is pending/incomplete has NO usable
      measurement: ``UNJUDGED`` with a named reason — never a silent 0/OK.
    * a session whose active model or capacity cannot be resolved is ``UNJUDGED`` — never a
      fabricated capacity, never OK.
    * a session whose last assistant message is a completed compaction summary is ``OK`` with
      the named post-compaction reason (mirroring the runtime, which skips its overflow check
      there) — the first resumed work is not blocked by the stale pre-compaction reading.
    * otherwise the shared capacity judgment.

    The judged session is the EXPLICIT identity; there is no most-recently-updated fallback.
    """
    report = measure_report(session_id, db_path=db_path, env=env)
    return report["verdict"], report["reason"], report["backend_available"]


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
                    "post_compaction": False, "capacity": None, "model": None}
    verdict, reason, capacity_block = _verdict_for(resolved)
    capacity_obj = resolved.get("capacity")
    capacity_valid = capacity_obj is not None
    post_compaction = bool(resolved.get("post_compaction")) and verdict == "OK"

    now = sc.utc_now()
    result: dict = {
        "schema": SCHEMA_ID,
        "ts": now,
        "session_id": session_id,
        "turns": int(resolved.get("turns") or 0),
        "context_tokens": int(resolved.get("context_tokens") or 0),
        "usage_incomplete": bool(resolved.get("usage_incomplete")) and verdict != "UNJUDGED",
        "post_compaction": post_compaction,
        "verdict": verdict,
        "reason": reason,
        "model": resolved.get("model"),
        "capacity": capacity_block or None,
        "remaining_tokens": (
            None if post_compaction
            else max(0, capacity_obj.effective_limit - int(resolved["context_tokens"]))
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
    if result.get("post_compaction"):
        budget = (
            f"post-compaction (pre-compaction reading {result['context_tokens']:,}; "
            f"measurement resumes with the next completed sample)"
        )
    elif capacity.get("effective_limit"):
        budget = (
            f"context {result['context_tokens']:,}/{capacity['effective_limit']:,} "
            f"(hard {capacity['hard_limit']:,}; response headroom "
            f"{capacity['response_headroom_tokens']:,}; compaction reserve "
            f"{capacity['compaction_reserved_tokens']:,}"
            + (f"; policy {capacity['policy_limit']:,}" if capacity.get("policy_limit") else "")
            + ")"
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
