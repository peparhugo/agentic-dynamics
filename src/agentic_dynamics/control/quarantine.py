"""Quarantine registry — the contamination ledger the analyze chain and the permanence gate read.

This module is the first half of phase 4 of the ``admission_leases`` work order
(``workflows/repository/admission_leases.yaml``); the watcher that *writes* into it lives in
:mod:`agentic_dynamics.control.lease_watchdog`. Nothing here invokes a model, kills a process,
or steers a session — it is a ledger with an opinion about what may be reused.

The problem it solves (the audit's item 8)
------------------------------------------
Phases 1–3 gave the system a way to refuse spend it cannot account for. They did not give it a
way to say anything about the *output* of work that ran anyway. A lease is a claim with an
expiry; when the expiry passes while the work is still running, whatever that work wrote is no
longer covered by a reservation. The audit's word for such output is **contaminated**:

    Contaminated ≠ wrong. It means *unaccounted-for* — produced outside the window the system
    reserved for it, so its cost, its provenance, and its relationship to the grid it belongs
    to are all unverified. Contaminated output is not deleted and not silently reused; it is
    marked, and every consumer that would otherwise fold it into an aggregate skips it.

Three quarantine handles, because contaminated work leaves output in three places
--------------------------------------------------------------------------------
:class:`QuarantineKind` names them, and they mirror the identity fields the admission record has
carried since phase 1 (``worktree_identity`` / ``result_namespace``) plus the ladder's rung id:

``WORKTREE``
    The code surface — a ``/tmp/exp_*`` or ``/tmp/wt_*`` worktree. Consumed by
    ``scripts/analyze_worktrees.py`` (Game Reports) and ``scripts/inventory.py`` (the data
    chain's first step), and surfaced at the permanence gate by ``scripts/system_snapshot.py``.

``RESULT_NAMESPACE``
    The data surface — the ``experiments/results/<namespace>`` tree a run's payloads land in.

``LADDER_RUNG``
    The grid surface — one rung of a ladder campaign (``infrastructure/docker-compose.ladder.yml``).
    A contaminated rung poisons the comparison it belongs to even when its own numbers look fine,
    because an arm that ran past its lease is not the arm the design specified.

Where the state lives, and why the JSONL is the authority
---------------------------------------------------------
Two surfaces, deliberately asymmetric:

**The durable JSONL** (``experiments/results/quarantine/quarantine.jsonl``) is the authority.
Append-only, one JSON object per line, both openings and lifts. It is a file, so a consumer in
the analyze chain can answer "is this worktree quarantined?" with no Redis, no network, and no
daemon — which matters because the alternative is an analysis pipeline that silently includes
contaminated worktrees whenever Redis happens to be down. That is the exact failure this ledger
exists to prevent, so the read path must not depend on the flakiest component.

**The Redis hash** (framework Redis, db 1 — never the story-agent sandbox on 6379) is the hot
path: the Control Room's board reads it, and a containerized cell that shares ``fleet-net`` but
not the host filesystem writes it. Reads therefore *union* the two surfaces when Redis is
reachable, and fall back to the JSONL alone when it is not — a best-effort widening of a
complete answer, never a dependency.

Write order mirrors ``scripts/supervise.py:emit_flag`` and
``control.orphan_sweep.record_orphan``: durable write first, hot path second (best-effort), so a
Redis outage can never erase a contamination record.

Fail-closed, and what that means for a *read*
---------------------------------------------
"Fail-closed" for admission means "refuse to spend". For quarantine it means **refuse to reuse**:

* An unreadable or corrupt quarantine ledger raises :class:`QuarantineLedgerError`. It is not
  treated as "no quarantines". A ledger we cannot parse tells us nothing about contamination,
  and answering "nothing is contaminated" to a question we cannot answer is the coercion this
  whole work order exists to delete (cf. absent cost → ``0.0``).
* A *missing* ledger file, by contrast, is legitimately empty: nothing has ever been
  quarantined. Absent and corrupt are different states, and are kept different here.

The consult helpers (:func:`is_worktree_quarantined` and friends) are the exception, and they
say so at their call sites: they are the convenience layer for scripts that must degrade rather
than crash, and they take an explicit ``on_error`` policy instead of picking one silently.

Advisory, not steering
----------------------
Quarantining marks; it never deletes a worktree, rewrites a result, or stops a session. The
supervisor rail is observe-only (``docs/architecture/current/supervisor_design.md``) and this
module inherits that constraint: the *consumers* decide what to do with the mark, and the
controller's permanence gate remains the only thing that makes anything permanent.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from agentic_dynamics.core.paths import PROJECT_ROOT

# ── Placement ────────────────────────────────────────────────────────────────────────────────

#: The durable ledger, relative to the repo root. Under ``experiments/results/`` beside the
#: supervisor's ``flags.jsonl`` and the sweep's ``orphans.jsonl`` — the same "durable observation
#: ledgers" neighbourhood, so an operator finds all three in one place.
QUARANTINE_DIR_REL = "experiments/results/quarantine"
QUARANTINE_LEDGER_REL = f"{QUARANTINE_DIR_REL}/quarantine.jsonl"

#: Absolute default. Overridable per-instance (tests) and by env (containers with a bind mount).
QUARANTINE_LEDGER_PATH = PROJECT_ROOT / QUARANTINE_LEDGER_REL

#: Env override for the ledger location — the container case, where the repo is mounted
#: elsewhere. Same convention as ``ORPHAN_SWEEP_*``.
LEDGER_PATH_ENV = "FINOPS_QUARANTINE_LEDGER"

#: The Redis hash holding currently-active quarantines, keyed ``<kind>/<identity>``. Bounded
#: implicitly by the number of distinct contaminated identities (a hash, not a growing list),
#: and lifted entries are deleted from it — so it stays the size of the live problem.
QUARANTINE_KEY = "finops:quarantine:active"

#: The bounded event list — every opening and lift, newest first, for the Control Room's board.
#: Separate from the hash because the hash answers "what is contaminated *now*" and the list
#: answers "what happened", and conflating them makes a lift indistinguishable from an amnesia.
QUARANTINE_EVENTS_KEY = "quarantine_events"
QUARANTINE_EVENTS_MAX = 200


# ── Vocabulary ───────────────────────────────────────────────────────────────────────────────


class QuarantineKind(str, Enum):
    """Which output surface an entry marks. See the module docstring for why there are three."""

    WORKTREE = "worktree"
    RESULT_NAMESPACE = "result_namespace"
    LADDER_RUNG = "ladder_rung"


class QuarantineReason(str, Enum):
    """Why the identity was marked — a closed vocabulary, so the board can group by cause.

    Closed rather than free-form because "why was this quarantined" is a question with a small
    number of correct answers, and a free-form string would drift into prose that no consumer
    can filter on. The human-readable detail goes in :attr:`QuarantineRecord.why`.
    """

    #: A BUDGET lease expired while the work was still producing output — the canonical case.
    #: The work outlived its spend reservation, so what it wrote is unaccounted-for.
    BUDGET_LEASE_EXPIRED = "budget_lease_expired"
    #: A CONCURRENCY lease expired. Normally only a *flag* (a slot overrun is a throughput
    #: problem, not a spend problem), but available as a reason for an operator who decides a
    #: particular overrun did contaminate its output.
    CONCURRENCY_LEASE_EXPIRED = "concurrency_lease_expired"
    #: The work ran with ``cost_source=unknown`` — it spent, and we cannot say how much.
    UNKNOWN_COST = "unknown_cost"
    #: Output found with no admission behind it at all (the bypass case).
    ADMISSION_BYPASS = "admission_bypass"
    #: An operator's judgement call. The escape hatch, named so it is visibly not automatic.
    MANUAL = "manual"


class QuarantineError(RuntimeError):
    """Base class for every quarantine-registry failure."""


class QuarantineLedgerError(QuarantineError):
    """The durable ledger could not be read or parsed — so contamination status is unknown.

    Loud by design: see the module docstring's fail-closed note. A corrupt ledger is never
    reported as "nothing is quarantined".
    """


class QuarantineFieldError(QuarantineError):
    """A record is missing a required field or carries the wrong type. Never defaulted away."""


# ── The record ───────────────────────────────────────────────────────────────────────────────


def _utc_now() -> float:
    """Epoch seconds (UTC). A seam so tests can drive time without sleeping."""
    return datetime.now(timezone.utc).timestamp()


def _iso(epoch: float) -> str:
    """Render epoch seconds as an ISO-8601 UTC string (what humans read on the board)."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


@dataclass(frozen=True)
class QuarantineRecord:
    """One contamination mark: what is contaminated, why, on whose evidence, and whether lifted.

    Frozen, like :class:`~agentic_dynamics.control.lease_registry.Lease`: a record is opened and
    then either stands or is lifted by a *new* record. Editing history in place would make the
    ledger unauditable, which defeats the point of an append-only ledger.
    """

    #: ``<kind>/<identity>`` — the Redis hash field and the de-duplication key.
    entry_id: str
    kind: QuarantineKind
    #: The handle: a worktree name (``wt_admission_leases``), a results namespace, or a rung id.
    #: Names, never paths — a path is machine-specific and a quarantine outlives the machine.
    identity: str
    reason: QuarantineReason
    #: Human-readable detail. The `reason` is for filtering; this is for understanding.
    why: str
    #: Epoch seconds when the contamination was detected.
    detected_at: float
    #: What produced this record: ``lease_watchdog`` | ``operator`` | a caller-chosen label.
    source: str
    #: The run whose lease expired, when known. Empty for an operator's manual mark.
    run_id: str = ""
    #: The expired lease ids that justified the mark — the audit trail back to the registry.
    lease_ids: tuple[str, ...] = ()
    #: The cost provenance in force (phase 3's vocabulary), as a plain string or ``None``.
    cost_source: str | None = None
    #: Free-form provenance (model, scope, campaign, phase…).
    metadata: dict[str, Any] = field(default_factory=dict)
    #: Set on the record that *lifts* a quarantine. An active record has ``lifted=False``.
    lifted: bool = False
    lifted_at: float | None = None
    #: Who lifted it. Required (non-empty) when ``lifted`` — a lift is an accountable act.
    lifted_by: str = ""
    #: Why it was lifted (re-measured, re-run under a valid lease, judged uncontaminated…).
    lift_reason: str = ""

    @property
    def detected_at_iso(self) -> str:
        """The detection timestamp as ISO-8601 UTC."""
        return _iso(self.detected_at)

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe projection — the exact shape written to the JSONL and to Redis."""
        return {
            "entry_id": self.entry_id,
            "kind": self.kind.value,
            "identity": self.identity,
            "reason": self.reason.value,
            "why": self.why,
            "detected_at": self.detected_at,
            "detected_at_iso": self.detected_at_iso,
            "source": self.source,
            "run_id": self.run_id,
            "lease_ids": list(self.lease_ids),
            "cost_source": self.cost_source,
            "metadata": dict(self.metadata),
            "lifted": self.lifted,
            "lifted_at": self.lifted_at,
            "lifted_by": self.lifted_by,
            "lift_reason": self.lift_reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> QuarantineRecord:
        """Rebuild a record, refusing anything malformed.

        A record that will not parse is a :class:`QuarantineFieldError`, never a skipped line:
        skipping would under-report contamination, and under-reporting contamination is exactly
        the silent reuse this ledger prevents. (The line-level caller decides whether to let
        that propagate — :meth:`QuarantineRegistry.entries` does, deliberately.)
        """
        required = ("entry_id", "kind", "identity", "reason", "detected_at", "source")
        missing = [k for k in required if payload.get(k) is None]
        if missing:
            raise QuarantineFieldError(f"quarantine record is missing field(s): {missing}")
        try:
            return cls(
                entry_id=str(payload["entry_id"]),
                kind=QuarantineKind(payload["kind"]),
                identity=str(payload["identity"]),
                reason=QuarantineReason(payload["reason"]),
                why=str(payload.get("why") or ""),
                detected_at=float(payload["detected_at"]),
                source=str(payload["source"]),
                run_id=str(payload.get("run_id") or ""),
                lease_ids=tuple(str(x) for x in (payload.get("lease_ids") or ())),
                cost_source=(
                    str(payload["cost_source"]) if payload.get("cost_source") else None
                ),
                metadata=dict(payload.get("metadata") or {}),
                lifted=bool(payload.get("lifted", False)),
                lifted_at=(
                    float(payload["lifted_at"]) if payload.get("lifted_at") is not None else None
                ),
                lifted_by=str(payload.get("lifted_by") or ""),
                lift_reason=str(payload.get("lift_reason") or ""),
            )
        except (ValueError, TypeError) as exc:
            raise QuarantineFieldError(f"quarantine record is malformed: {exc}") from exc

    def validate(self) -> None:
        """Raise unless the record is complete. Collects every problem before raising."""
        problems: list[str] = []
        if not self.identity.strip():
            problems.append("identity must be a non-empty string")
        if not self.source.strip():
            problems.append("source must be a non-empty string")
        if not self.why.strip():
            # A mark with no explanation is unreviewable — an operator reading the board six
            # weeks later has no way to judge it, so the lift decision becomes a coin flip.
            problems.append("why must be a non-empty string (an unexplained mark is unreviewable)")
        if self.lifted and not self.lifted_by.strip():
            problems.append("a lifted record must name who lifted it (lifted_by)")
        if self.lifted and self.lifted_at is None:
            problems.append("a lifted record must carry lifted_at")
        if problems:
            raise QuarantineFieldError(
                f"quarantine record {self.entry_id!r} is not valid: " + "; ".join(problems)
            )


def entry_id_for(kind: QuarantineKind, identity: str) -> str:
    """The stable key for one contaminated identity: ``<kind>/<identity>``.

    Stable (not a uuid) so that re-detecting the same contamination is *idempotent* — the
    watchdog runs on a cadence and must not open a hundred records for one stuck worktree.
    """
    return f"{kind.value}/{identity}"


# ── The registry ─────────────────────────────────────────────────────────────────────────────


class QuarantineRegistry:
    """Read/write access to the contamination ledger. Durable-first, Redis best-effort.

    Constructing one is cheap and does no I/O: the ledger is read lazily, and the Redis client
    is whatever the caller passes (``None`` for the pure-file mode the analyze chain uses).
    """

    def __init__(
        self,
        *,
        ledger_path: str | Path | None = None,
        redis_client: Any = None,
        now_fn: Any = None,
    ) -> None:
        """
        :param ledger_path: durable JSONL. Defaults to the env override, else the repo default.
        :param redis_client: optional framework-Redis client for the hot path. ``None`` disables
            it entirely — the registry is fully functional without Redis, by design.
        :param now_fn: clock seam returning epoch seconds; defaults to wall-clock UTC.
        """
        self._path = Path(
            ledger_path
            or os.environ.get(LEDGER_PATH_ENV, "").strip()
            or QUARANTINE_LEDGER_PATH
        )
        self._redis = redis_client
        self._now_fn = now_fn or _utc_now

    @property
    def ledger_path(self) -> Path:
        """Where the durable ledger lives — surfaced so an operator can be told the path."""
        return self._path

    # -- reads -------------------------------------------------------------------------------

    def entries(self) -> list[QuarantineRecord]:
        """Every record on the durable ledger, oldest first — openings and lifts alike.

        A missing file is an empty ledger (nothing has been quarantined yet). An *unreadable* or
        *unparseable* file raises :class:`QuarantineLedgerError`: see the fail-closed note.
        """
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        except OSError as exc:
            raise QuarantineLedgerError(
                f"quarantine ledger {self._path} could not be read — contamination status is "
                f"unknown, so nothing may be assumed clean: {exc}"
            ) from exc

        records: list[QuarantineRecord] = []
        for lineno, line in enumerate(raw.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise QuarantineLedgerError(
                    f"quarantine ledger {self._path} line {lineno} is not valid JSON — the "
                    f"ledger cannot be trusted to list every contaminated identity: {exc}"
                ) from exc
            records.append(QuarantineRecord.from_dict(payload))
        return records

    def _redis_entries(self) -> list[QuarantineRecord]:
        """Active records from the Redis hash — best-effort, never raising.

        Best-effort because Redis is the *widening* surface here: it can only add identities the
        file did not know about (a container that could not write the host filesystem). A failure
        to read it therefore narrows the answer to the authoritative file rather than
        invalidating it, which is the one direction that stays safe.
        """
        if self._redis is None:
            return []
        try:
            raw = self._redis.hgetall(QUARANTINE_KEY) or {}
        except Exception:  # noqa: BLE001 — the file is the authority; Redis only widens it
            return []
        records: list[QuarantineRecord] = []
        for value in raw.values():
            try:
                payload = json.loads(value.decode() if isinstance(value, bytes) else value)
                records.append(QuarantineRecord.from_dict(payload))
            except (ValueError, TypeError, QuarantineError):
                # One corrupt hash field must not hide the rest of the live quarantines. Unlike
                # the file path this is not a trust boundary: the file already gave a complete
                # authoritative answer, and this loop is only adding to it.
                continue
        return records

    def active(self, kind: QuarantineKind | None = None) -> list[QuarantineRecord]:
        """Currently-contaminated identities: opened, not since lifted.

        Resolution: replay the durable ledger in order (later records win for the same
        ``entry_id``), then union in Redis-only identities. Ordering is by detection time, so a
        board renders oldest contamination first.
        """
        latest: dict[str, QuarantineRecord] = {}
        for record in self.entries():
            latest[record.entry_id] = record
        for record in self._redis_entries():
            # The file wins on conflict: it is the authority, and a stale hash entry (written
            # before a lift that only the file recorded) must not resurrect a lifted quarantine.
            latest.setdefault(record.entry_id, record)

        live = [r for r in latest.values() if not r.lifted]
        if kind is not None:
            live = [r for r in live if r.kind is kind]
        return sorted(live, key=lambda r: (r.detected_at, r.entry_id))

    def is_quarantined(self, kind: QuarantineKind, identity: str) -> bool:
        """True when ``identity`` is currently contaminated for ``kind``."""
        target = entry_id_for(kind, identity)
        return any(r.entry_id == target for r in self.active(kind))

    def active_identities(self, kind: QuarantineKind) -> set[str]:
        """The contaminated identities of one kind — the set a consumer filters against.

        Returned as a set because every consumer's question is membership, and handing back a
        set makes the filtering site a one-liner that cannot accidentally become O(n²).
        """
        return {r.identity for r in self.active(kind)}

    # -- writes ------------------------------------------------------------------------------

    def quarantine(
        self,
        kind: QuarantineKind,
        identity: str,
        *,
        reason: QuarantineReason,
        why: str,
        source: str = "operator",
        run_id: str = "",
        lease_ids: Sequence[str] = (),
        cost_source: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> QuarantineRecord | None:
        """Open a quarantine. Idempotent: returns ``None`` if the identity is already marked.

        Idempotence is load-bearing — the watchdog runs every few minutes and will re-observe
        the same expired lease until an operator acts on it. Re-recording would turn one stuck
        worktree into an unbounded ledger, and the *first* detection time is the one that
        matters for judging how long contamination went unnoticed, so the earliest record wins.

        Durable write first, Redis second (best-effort). A Redis outage costs the board its
        freshness; it never costs the ledger its record.
        """
        record = QuarantineRecord(
            entry_id=entry_id_for(kind, identity),
            kind=kind,
            identity=identity,
            reason=reason,
            why=why,
            detected_at=self._now_fn(),
            source=source,
            run_id=run_id,
            lease_ids=tuple(lease_ids),
            cost_source=cost_source,
            metadata=dict(metadata or {}),
        )
        record.validate()

        if self.is_quarantined(kind, identity):
            return None

        self._append(record)
        self._mirror_active(record)
        return record

    def lift(
        self,
        kind: QuarantineKind,
        identity: str,
        *,
        lifted_by: str,
        lift_reason: str,
    ) -> QuarantineRecord | None:
        """Clear a quarantine by appending a lift record. ``None`` if it was not active.

        A lift never rewrites or removes the opening record: the ledger keeps both, so "this
        worktree was contaminated for nine days and then cleared by X because Y" stays legible.
        Only the Redis hash — which answers "what is contaminated *now*" — loses the field.
        """
        existing = next(
            (r for r in self.active(kind) if r.identity == identity), None
        )
        if existing is None:
            return None

        now = self._now_fn()
        lifted = QuarantineRecord(
            entry_id=existing.entry_id,
            kind=existing.kind,
            identity=existing.identity,
            reason=existing.reason,
            why=existing.why,
            detected_at=existing.detected_at,
            source=existing.source,
            run_id=existing.run_id,
            lease_ids=existing.lease_ids,
            cost_source=existing.cost_source,
            metadata={**existing.metadata, "lifted_from": existing.entry_id},
            lifted=True,
            lifted_at=now,
            lifted_by=lifted_by,
            lift_reason=lift_reason,
        )
        lifted.validate()

        self._append(lifted)
        if self._redis is not None:
            try:
                self._redis.hdel(QUARANTINE_KEY, lifted.entry_id)
                self._push_event(lifted)
            except Exception:  # noqa: BLE001 — the durable lift already landed
                pass
        return lifted

    # -- persistence helpers -----------------------------------------------------------------

    def _append(self, record: QuarantineRecord) -> None:
        """Append one record to the durable ledger, creating the directory on first use."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(payload + "\n")

    def _mirror_active(self, record: QuarantineRecord) -> None:
        """Mirror an opening into the Redis hot path + event list. Best-effort by contract."""
        if self._redis is None:
            return
        payload = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
        try:
            self._redis.hset(QUARANTINE_KEY, record.entry_id, payload)
            self._push_event(record)
        except Exception:  # noqa: BLE001 — the durable write already succeeded
            pass

    def _push_event(self, record: QuarantineRecord) -> None:
        """Push one bounded event onto the hot list (newest first). Caller handles failure."""
        payload = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
        self._redis.lpush(QUARANTINE_EVENTS_KEY, payload)
        self._redis.ltrim(QUARANTINE_EVENTS_KEY, 0, QUARANTINE_EVENTS_MAX - 1)


# ── The consult layer (what the analyze chain and the permanence gate call) ──────────────────


def default_registry(**kwargs: Any) -> QuarantineRegistry:
    """A registry on the repo default ledger, with no Redis unless the caller supplies one.

    The no-Redis default is deliberate: every *consult* site (analyze, inventory, the snapshot)
    only needs the authoritative file, and giving them a Redis dependency they do not need would
    make the data chain fail in a new way for no gain.
    """
    return QuarantineRegistry(**kwargs)


def quarantined_identities(
    kind: QuarantineKind,
    *,
    registry: QuarantineRegistry | None = None,
    on_error: str = "raise",
) -> set[str]:
    """The contaminated identities of one kind, for a consult site.

    ``on_error`` is explicit rather than defaulted-away because the two consult populations want
    different things and neither should get the other's behaviour by accident:

    ``"raise"`` (default)
        For anything that produces a *published* aggregate. An unreadable ledger means unknown
        contamination, and an aggregate built on unknown contamination is worse than no
        aggregate — it looks authoritative.

    ``"empty"``
        For a *display* surface (the game board, a dashboard). A snapshot that crashes because
        the quarantine ledger is corrupt is a worse operator experience than one that renders
        and says nothing about quarantine; the operator still has the ledger error elsewhere.
    """
    reg = registry or default_registry()
    try:
        return reg.active_identities(kind)
    except QuarantineError:
        if on_error == "empty":
            return set()
        raise


def is_worktree_quarantined(
    name: str,
    *,
    registry: QuarantineRegistry | None = None,
) -> bool:
    """True when a worktree (by *name*, e.g. ``wt_admission_leases``) is contaminated."""
    return (registry or default_registry()).is_quarantined(QuarantineKind.WORKTREE, name)


def filter_quarantined_paths(
    paths: Iterable[str],
    *,
    registry: QuarantineRegistry | None = None,
    on_error: str = "raise",
) -> tuple[list[str], list[str]]:
    """Split worktree *paths* into ``(kept, excluded)`` by quarantine status.

    Takes paths and matches on ``Path(p).name`` because every worktree consumer in the repo
    globs paths (``WORKTREE_GLOB``) while the ledger stores machine-independent names. Doing the
    conversion here means each call site is one line and none of them re-derive the rule.

    Returns both halves rather than just the survivors so the caller can *report* the exclusion.
    Silent exclusion would be its own integrity problem: a corpus that quietly shrank is
    indistinguishable from one that was never that big.
    """
    excluded_names = quarantined_identities(
        QuarantineKind.WORKTREE, registry=registry, on_error=on_error
    )
    kept: list[str] = []
    excluded: list[str] = []
    for path in paths:
        (excluded if Path(path).name in excluded_names else kept).append(path)
    return kept, excluded


def quarantine_board(registry: QuarantineRegistry | None = None) -> dict[str, Any]:
    """Project live quarantine state for the Control Room, beside the admission board.

    Total and read-only: an unreadable ledger reports itself as an ``error`` row rather than
    raising, because a dashboard's job is to *show* the broken state, not to disappear with it.
    """
    reg = registry or default_registry()
    try:
        active = reg.active()
    except QuarantineError as exc:
        return {"error": str(exc), "ledger": str(reg.ledger_path), "kinds": {}, "total": 0}
    by_kind: dict[str, list[dict[str, Any]]] = {kind.value: [] for kind in QuarantineKind}
    for record in active:
        by_kind[record.kind.value].append(record.to_dict())
    return {
        "ledger": str(reg.ledger_path),
        "kinds": by_kind,
        "total": len(active),
    }


# ── Iteration helper (used by the watchdog and by tests) ─────────────────────────────────────


def iter_ledger(path: str | Path) -> Iterator[QuarantineRecord]:
    """Stream a ledger file record by record — for tooling that must not hold it all in memory."""
    yield from QuarantineRegistry(ledger_path=path).entries()


def new_entry_token() -> str:
    """A short opaque token for metadata that wants uniqueness (never an ``entry_id``).

    Kept separate from :func:`entry_id_for` so nobody reaches for a uuid where the *stable*
    identity key is required — a random entry id would silently break idempotence.
    """
    return uuid.uuid4().hex[:12]
