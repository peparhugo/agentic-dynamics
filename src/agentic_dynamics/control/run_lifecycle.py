"""The run lifecycle rails: the run heartbeat + the zombie-run sweep (``control_db_evidence`` e2).

Why this module exists
----------------------
A control run's ``state = 'running'`` row says "the orchestrator *started* work", never "the
orchestrator is *still* alive". A killed runner leaves that row dangling forever (proven
2026-09-02: two killed runs needed manual cancellation via ``transition_run``), polluting the
packet's ``active_runs`` and, because every transition bumps the epoch, inflating the epoch with
transitions that describe nothing real.

This module closes that hole with two pieces that share one liveness model:

1. **The run heartbeat** (:class:`RunHeartbeatThread`). The orchestrator's composition root
   (``scripts/run_workflow.py``) starts a daemon thread while its run is executing; the thread
   upserts the run's ``run_heartbeats`` row (``control_db.record_run_heartbeat``) every few
   seconds. The thread lives only as long as the orchestrator process does — kill the process
   and the beats stop. A beat is deliberately NOT a state transition: it never touches
   ``runs``/``run_transitions`` and never bumps the control epoch (see
   :meth:`ControlDB.record_run_heartbeat`), so a heartbeat every N seconds cannot read as a
   stream of durable state changes to a master diffing packets.
2. **The zombie-run sweep** (:func:`sweep_zombie_runs`, exposed as ``agentic-dynamics control
   sweep-zombies``). Finds ``running`` runs whose heartbeat has *expired* — ``last_seen_at``
   older than the staleness window — and transitions each to ``CANCELLED`` with a reason, through
   the legitimate transition API (:meth:`ControlDB.transition_run`, governed by
   :data:`control_db.ALLOWED_TRANSITIONS`). Never raw SQL: the ``run_transitions`` log is
   append-only by design, and the sweep is not a second implementation of the state machine.

The sweep's liveness vocabulary is deliberately three-valued, because "we cannot tell" must not
collapse into either of the actionable answers:

* ``live`` — the run has a heartbeat row whose ``last_seen_at`` is inside the staleness window.
  The sweep never touches it.
* ``zombie`` — the run has a heartbeat row whose ``last_seen_at`` has expired. The sweep
  transitions it to ``CANCELLED``.
* ``unknown`` — the run has NO heartbeat row at all (a pre-e2 run, or one whose orchestrator died
  before its first beat). There is no evidence of death, only an absence of evidence of life, so
  the sweep leaves it alone and reports it. A sweep that cancelled on an absent heartbeat would
  be guessing, and a guess that cancels a live run is the one failure this module exists to
  prevent.

The whole module is flag/transition-only in the supervisor sense: it transitions stale runs (via
the database's own enforced graph) and reports; it never kills, resumes, or re-routes a live run.

The heartbeat thread is strictly best-effort: a failed beat is logged and swallowed, never raised
— a bookkeeping store's outage must not fail the run whose bookkeeping it is (e2 VERIFY d). The
sweep is exception-contained per run for the same reason: one run's transition failure is
reported in the sweep's ``errors``, never allowed to abort the pass over the remaining runs.
"""

from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agentic_dynamics.control.control_db import ControlDB, ControlDBError, RunState

#: How often the orchestrator's heartbeat thread beats, in seconds. Small relative to the
#: staleness window so a healthy run stays comfortably inside it even across a slow phase.
DEFAULT_HEARTBEAT_INTERVAL_S = 30

#: How old a run's last heartbeat must be before the sweep treats it as a zombie, in seconds.
#: Deliberately larger than a few heartbeat intervals: the sweep must tolerate a transient beat
#: failure (a busy database) without cancelling a live run — the asymmetry that makes "cancelled"
#: mean "almost certainly dead", not "briefly unlucky".
DEFAULT_STALE_AFTER_S = 600

#: Environment overrides (see the module docstring for the defaults' reasoning).
HEARTBEAT_INTERVAL_ENV = "FINOPS_RUN_HEARTBEAT_S"
STALE_AFTER_ENV = "FINOPS_RUN_STALE_S"

#: The actor stamped on every cancellation the sweep performs.
SWEEP_ACTOR = "zombie-sweep"


def _env_seconds(name: str, default: int) -> int:
    """Read a positive-integer seconds override, falling back to ``default``."""
    try:
        value = int(os.environ.get(name, "").strip())
    except ValueError:
        return default
    return value if value >= 1 else default


def heartbeat_interval_s() -> int:
    """The heartbeat cadence, seconds (env ``FINOPS_RUN_HEARTBEAT_S`` overrides)."""
    return _env_seconds(HEARTBEAT_INTERVAL_ENV, DEFAULT_HEARTBEAT_INTERVAL_S)


def stale_after_s() -> int:
    """The zombie staleness window, seconds (env ``FINOPS_RUN_STALE_S`` overrides)."""
    return _env_seconds(STALE_AFTER_ENV, DEFAULT_STALE_AFTER_S)


def _iso(moment: datetime) -> str:
    """UTC ISO-8601 with a ``Z`` suffix — byte-for-byte ``control_db._now()``'s shape.

    The staleness check is a SQL-free string comparison (``last_seen_at < cutoff``), and string
    ordering only tracks time ordering if every stamp shares one format — the same rule
    ``outbox._iso`` documents for its own backoff comparison.
    """
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# ── The sweep's report ───────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ZombieSweepReport:
    """The outcome of one :func:`sweep_zombie_runs` pass — every ``running`` run accounted for.

    The three classification buckets (``live``/``unknown``/``cancelled``/``would_cancel``) plus
    ``errors`` partition the runs the pass examined, mirroring ``DrainReport``'s
    the-parts-add-up-to-the-whole discipline: a summary that silently drops runs it could not
    classify is how "we swept everything" quietly becomes "we swept what did not error".
    """

    #: ``running`` runs the pass examined.
    examined: int = 0
    #: Runs transitioned to ``cancelled`` this pass — one entry per transition.
    cancelled: tuple[dict[str, str], ...] = ()
    #: Runs that WOULD be cancelled but for ``dry_run`` (same shape as ``cancelled`` entries).
    would_cancel: tuple[dict[str, str], ...] = ()
    #: Runs left untouched because their heartbeat is fresh.
    live: tuple[str, ...] = ()
    #: Runs left untouched because they have no heartbeat row (no liveness information).
    unknown: tuple[str, ...] = ()
    #: Per-run failures (a transition refused, a transient database error) — the pass continued.
    errors: tuple[str, ...] = ()

    @property
    def zombie_ids(self) -> tuple[str, ...]:
        """The runs judged dead, whether or not this pass cancelled them (dry-run aware)."""
        acted = self.cancelled + self.would_cancel
        return tuple(entry["run_id"] for entry in acted)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready rendering (what the CLI prints and an operator or watchdog can read)."""
        return {
            "examined": self.examined,
            "cancelled": list(self.cancelled),
            "would_cancel": list(self.would_cancel),
            "live": list(self.live),
            "unknown": list(self.unknown),
            "errors": list(self.errors),
        }


# ── The sweep ────────────────────────────────────────────────────────────────────────────────


def _staleness_cutoff(moment: datetime, stale_after_seconds: int) -> str:
    """The ISO stamp before which a heartbeat reads as expired."""
    return _iso(moment - timedelta(seconds=stale_after_seconds))


def classify_running_run(
    run: Any,
    heartbeat: Any,
    *,
    cutoff: str,
) -> str:
    """Classify one ``running`` run against the staleness cutoff: ``live``/``zombie``/``unknown``.

    Kept as a named helper so the classification rule is a single, testable statement: a run
    with no heartbeat row is ``unknown`` (not ``zombie``); a run whose last heartbeat predates
    the cutoff is ``zombie``; anything else is ``live``.
    """
    if heartbeat is None:
        return "unknown"
    if heartbeat.last_seen_at < cutoff:
        return "zombie"
    return "live"


def sweep_zombie_runs(
    db: ControlDB,
    *,
    stale_after_seconds: int | None = None,
    actor: str = SWEEP_ACTOR,
    dry_run: bool = False,
    now: datetime | None = None,
) -> ZombieSweepReport:
    """Transition every stale ``running`` run to ``CANCELLED``; return an accounting.

    Eligibility is read from the database in one consistent snapshot (``db.runs(state=running)``),
    then each candidate is judged against its heartbeat row:

    * a **fresh** heartbeat (``last_seen_at >= cutoff``) → ``live``, untouched;
    * an **expired** heartbeat (``last_seen_at < cutoff``) → ``zombie``: transitioned to
      ``CANCELLED`` with a reason naming the staleness evidence, via :meth:`ControlDB.transition_run`
      — the legitimate API over the same ``ALLOWED_TRANSITIONS`` graph the packet's ``safe_actions``
      derive from, never raw SQL;
    * **no** heartbeat row → ``unknown``, untouched and reported (see the module docstring).

    ``dry_run`` reports the zombies the pass *would* cancel without transitioning anything, so an
    operator can preview the sweep before letting it act. A per-run transition failure
    (:class:`~agentic_dynamics.control.control_db.ControlDBError` — a run that just ended between
    the snapshot and the transition, a busy database) is recorded in ``errors`` and the pass
    continues: the sweep must never fail a run, live or zombie, because of one row's refusal.
    """
    stale = DEFAULT_STALE_AFTER_S if stale_after_seconds is None else int(stale_after_seconds)
    moment = now or datetime.now(timezone.utc)
    cutoff = _staleness_cutoff(moment, stale)
    reason_note = f"stale_after={stale}s (cutoff {cutoff})"

    running = db.runs(state=RunState.RUNNING)
    cancelled: list[dict[str, str]] = []
    would_cancel: list[dict[str, str]] = []
    live: list[str] = []
    unknown: list[str] = []
    errors: list[str] = []

    for run in running:
        heartbeat = db.run_heartbeat(run.run_id)
        verdict = classify_running_run(run, heartbeat, cutoff=cutoff)
        if verdict == "live":
            live.append(run.run_id)
            continue
        if verdict == "unknown":
            unknown.append(run.run_id)
            continue
        reason = (
            f"zombie run: last heartbeat {heartbeat.last_seen_at} "
            f"(beat {heartbeat.beat_count}) is older than {reason_note}"
        )
        if dry_run:
            would_cancel.append(
                {"run_id": run.run_id, "from_state": run.state.value, "reason": reason}
            )
            continue
        try:
            db.transition_run(run.run_id, RunState.CANCELLED, reason=reason, actor=actor)
        except ControlDBError as exc:
            errors.append(f"{run.run_id}: {exc}")
            continue
        cancelled.append(
            {"run_id": run.run_id, "from_state": run.state.value, "reason": reason}
        )

    return ZombieSweepReport(
        examined=len(running),
        cancelled=tuple(cancelled),
        would_cancel=tuple(would_cancel),
        live=tuple(live),
        unknown=tuple(unknown),
        errors=tuple(errors),
    )


# ── The heartbeat thread (orchestrator-side, wired at the composition root) ──────────────────


class RunHeartbeatThread:
    """A daemon thread that proves this process's run is alive, until the process is not.

    The orchestrator's run row is ``running`` from the moment the composition root records it;
    this thread keeps its ``run_heartbeats`` row fresh for as long as THIS process runs the
    engine. When the process is killed, the thread dies with it and the beats stop — which is
    exactly the signal the sweep needs: an expired heartbeat is the positive evidence that the
    orchestrator is gone, as opposed to a ``running`` row that merely says it once started.

    Deliberately a daemon thread owned by the composition root rather than machinery inside
    ``runtime.workflow_runner``: the heartbeat is control-plane bookkeeping (a tier-2 concern),
    and the engine must never import ``control`` (Debt-2). The thread opens its OWN
    ``ControlDB`` handle per beat — a sqlite connection is not shareable across threads by
    default — and every failure is logged and swallowed: a bookkeeping outage must never fail the
    run it is keeping book for (e2 VERIFY d).
    """

    def __init__(
        self,
        db_path: str | Path,
        run_id: str,
        *,
        interval_s: int | None = None,
        actor: str = "orchestrator",
        log: Any = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.run_id = run_id
        self.interval_s = heartbeat_interval_s() if interval_s is None else int(interval_s)
        self.actor = actor
        self._log = log or (lambda msg: print(f"run-heartbeat: {msg}", file=sys.stderr))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Begin beating. Idempotent: a started thread is not started twice."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        thread = threading.Thread(
            target=self._loop,
            name=f"run-heartbeat-{self.run_id}",
            daemon=True,
        )
        self._thread = thread
        thread.start()

    def stop(self) -> None:
        """Stop beating and wait for the thread to finish (bounded, so a stuck beat cannot hang).

        Safe to call twice and safe to call on an unstarted thread. The join timeout is the
        interval plus a small margin: a beat in flight when ``stop`` is called (e.g. blocked on
        the database) must not hang a run's terminal write.
        """
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(2.0, float(self.interval_s) + 1.0))

    def _loop(self) -> None:
        """Beat immediately (a run may be shorter than one interval), then every interval."""
        while True:
            self._beat()
            if self._stop.wait(self.interval_s):
                return

    def _beat(self) -> None:
        """One heartbeat write. Best-effort by contract — never raises."""
        try:
            with ControlDB.open(self.db_path) as db:
                db.record_run_heartbeat(self.run_id, actor=self.actor)
        except Exception as exc:  # noqa: BLE001 — a failed beat is logged, never a run failure
            self._log(
                f"write failed for {self.run_id} "
                f"({type(exc).__name__}: {exc}) — beat skipped, best-effort"
            )
