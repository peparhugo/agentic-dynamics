"""The command journal's script-side helper (step 10) — intent before act, receipt after.

The control database has carried a ``command_journal`` (step 2e) with **zero callers** since it
landed: ``scripts/promote.py`` and ``scripts/publish_release.py`` — the two permanence commands
— emitted knowledge-layer observations but never left a durable intent/receipt row. This module
is that caller's mechanism, shared so both commands journal IDENTICALLY (one implementation, the
same act-key discipline).

Semantics:

* ``begin_command`` records the INTENT under the act's idempotency key **before** any external
  effect. A repeated call for the same act:
  - finds a row still in ``intent`` -> returns it (a prior attempt recorded its intent and
    never an outcome — a crash between the two, which IS the evidence the journal preserves);
  - finds a terminal row -> advances to a new suffixed key (this is a NEW attempt of the same
    act: a failed push retried, a publication re-deployed after a host failure);
  - finds nothing -> records a fresh intent.
* ``finish_command`` records the observed outcome (``completed`` / ``failed`` / ``refused``).

Failure policy is asymmetric BY DESIGN:

* ``begin_command`` raises :class:`CommandJournalError` — an unrecordable intent means the act
  must not start ("recording is part of the act").
* ``finish_command`` returns a warning string instead of raising — the external effect has
  already landed, and an exception here would invite an unwind of something that happened. A
  missing receipt leaves the intent row in state ``intent``, which is exactly the crash
  evidence the journal exists to preserve.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

try:
    import _bootstrap  # noqa: F401  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: F401

from agentic_dynamics.control.control_db import (  # noqa: E402
    CommandRecord,
    ControlDB,
    ControlDBError,
)


class CommandJournalError(RuntimeError):
    """The command journal could not record the intent — the act must not start."""


def begin_command(
    db_path: str | Path | None,
    *,
    verb: str,
    actor: str,
    rationale: str,
    act_key: str,
    rationale_ref: str = "",
    run_id: str = "",
    candidate_sha: str = "",
    target_kind: str = "",
    target_id: str = "",
    detail: dict[str, Any] | None = None,
    completed: str = "return",
) -> CommandRecord:
    """Record the command's INTENT (or reuse/advance to the right row). Raises on failure.

    ``act_key`` is the stable identity of the act (verb + target + candidate); the helper owns
    the per-attempt suffixing so callers never think about it.

    ``completed`` — the PER-VERB replay policy for an act whose row is already ``completed``:

    * ``"return"`` (default, fail-safe): return the completed row so the CALLER decides. A
      promote uses this to refuse a duplicate push (its guard inspects ``state``); a new
      attempt must never be manufactured behind a finished act.
    * ``"advance"``: treat the completed row as a prior attempt and mint a new suffixed one —
      for verbs whose re-execution is a legitimate recovery (a publication re-deployed after
      a host failure).

    ``failed``/``refused`` rows ALWAYS advance: a retry after a recorded failure is a new
    authorized attempt of the same act, not a replay.
    """
    if completed not in ("return", "advance"):
        raise CommandJournalError(f"completed must be 'return' or 'advance', got {completed!r}")
    if not actor.strip():
        raise CommandJournalError("the command journal requires an actor — an anonymous intent is not a record")
    try:
        with ControlDB.open(db_path) as db:
            suffix = 1
            while suffix <= 99:
                key = act_key if suffix == 1 else f"{act_key}#{suffix}"
                existing = next(
                    (c for c in db.commands() if c.idempotency_key == key), None
                )
                if existing is None:
                    return db.record_command_intent(
                        verb,
                        actor=actor,
                        rationale=rationale,
                        rationale_ref=rationale_ref,
                        run_id=run_id,
                        candidate_sha=candidate_sha,
                        target_kind=target_kind,
                        target_id=target_id,
                        idempotency_key=key,
                        detail=detail,
                    )
                if existing.state == "intent":
                    # A prior attempt recorded its intent and never an outcome (a crash between
                    # intent and receipt). Reuse the row: the receipt below resolves it, and the
                    # first attempt's evidence survives on the row.
                    return existing
                if existing.state == "completed" and completed == "return":
                    # The act is DONE. Return the row so the caller's guard can refuse; never
                    # manufacture a second intent behind a finished act (the review's replay
                    # reproduction: promote's guard could never fire when this advanced).
                    return existing
                suffix += 1  # failed/refused (always) or completed under "advance"
            raise CommandJournalError(
                f"command journal: too many attempts recorded for act {act_key!r} (99)"
            )
    except (ControlDBError, OSError, sqlite3.Error) as exc:
        # ANY recording failure refuses the act, with a message the caller can carry: a
        # journal that cannot be written must never look like a journal that was.
        raise CommandJournalError(f"command journal unavailable: {exc}") from exc


def finish_command(
    db_path: str | Path | None,
    *,
    command_id: str,
    state: str,
    receipt: dict[str, Any] | None = None,
) -> str | None:
    """Record the command's outcome. ``None`` on success, a warning string on failure."""
    try:
        with ControlDB.open(db_path) as db:
            db.complete_command(command_id, state=state, receipt=receipt)
        return None
    except (ControlDBError, OSError, sqlite3.Error) as exc:
        return (
            f"could not record the command receipt for {command_id} (state {state!r}): {exc} "
            f"— the intent row remains as the evidence"
        )
