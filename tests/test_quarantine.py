"""Quarantine-registry tests — the contamination ledger, driven in both directions.

Both directions means: for every rule the registry states, one test proves it *marks* what it
should and one proves it *does not mark* what it should not — and, for the consult sites, one
test proves a quarantined identity is excluded and one proves a clean identity survives. A
quarantine that excluded everything would pass a naive "is it excluded?" test while destroying
the corpus, so the negative half is where the value is.

Storage is real (a ``tmp_path`` JSONL); Redis is faked, and only for the hot-path assertions.
The durable file is the authority under test, exactly as it is in production.
"""

from __future__ import annotations

import json

import pytest

from agentic_dynamics.control.quarantine import (
    QUARANTINE_EVENTS_KEY,
    QUARANTINE_KEY,
    QuarantineFieldError,
    QuarantineKind,
    QuarantineLedgerError,
    QuarantineReason,
    QuarantineRecord,
    QuarantineRegistry,
    entry_id_for,
    filter_quarantined_paths,
    is_worktree_quarantined,
    quarantine_board,
    quarantined_identities,
)

# ── Fakes ────────────────────────────────────────────────────────────────────────────────────


class FakeRedis:
    """Minimal hash + list double. Only the commands the registry issues are implemented."""

    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.lists: dict[str, list[str]] = {}
        #: Raised by every command when set — the "Redis is down" simulation.
        self.fail_with: Exception | None = None

    def _check(self) -> None:
        if self.fail_with is not None:
            raise self.fail_with

    def hgetall(self, key: str) -> dict[str, str]:
        self._check()
        return dict(self.hashes.get(key, {}))

    def hset(self, key: str, field: str, value: str) -> int:
        self._check()
        self.hashes.setdefault(key, {})[field] = value
        return 1

    def hdel(self, key: str, *fields: str) -> int:
        self._check()
        bucket = self.hashes.get(key, {})
        return sum(1 for f in fields if bucket.pop(f, None) is not None)

    def lpush(self, key: str, value: str) -> int:
        self._check()
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    def ltrim(self, key: str, start: int, end: int) -> bool:
        self._check()
        self.lists[key] = self.lists.get(key, [])[start:end + 1]
        return True


@pytest.fixture()
def ledger(tmp_path):
    """A registry on an isolated ledger with a frozen clock (so timestamps are assertable)."""
    clock = {"now": 1_000_000.0}
    registry = QuarantineRegistry(
        ledger_path=tmp_path / "quarantine.jsonl", now_fn=lambda: clock["now"]
    )
    return registry, clock


# ── Opening a quarantine ─────────────────────────────────────────────────────────────────────


def test_quarantine_marks_the_identity_and_writes_the_durable_ledger(ledger):
    """GRANT direction: an opened quarantine is active and lands on disk."""
    registry, _clock = ledger
    record = registry.quarantine(
        QuarantineKind.WORKTREE,
        "wt_contaminated",
        reason=QuarantineReason.BUDGET_LEASE_EXPIRED,
        why="budget lease expired mid-run",
        source="lease_watchdog",
        run_id="run-1",
        lease_ids=("lease-a",),
    )

    assert record is not None
    assert record.entry_id == entry_id_for(QuarantineKind.WORKTREE, "wt_contaminated")
    assert registry.is_quarantined(QuarantineKind.WORKTREE, "wt_contaminated")
    assert registry.active_identities(QuarantineKind.WORKTREE) == {"wt_contaminated"}

    # The durable line is real JSON with the full record, not a summary.
    lines = registry.ledger_path.read_text().strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["identity"] == "wt_contaminated"
    assert payload["reason"] == "budget_lease_expired"
    assert payload["lease_ids"] == ["lease-a"]
    assert payload["lifted"] is False


def test_a_clean_identity_is_not_quarantined(ledger):
    """REFUSE direction: marking one worktree must not mark its neighbours."""
    registry, _clock = ledger
    registry.quarantine(
        QuarantineKind.WORKTREE,
        "wt_contaminated",
        reason=QuarantineReason.BUDGET_LEASE_EXPIRED,
        why="expired",
    )
    assert not registry.is_quarantined(QuarantineKind.WORKTREE, "wt_clean")
    # …nor the same name under a different kind: the kinds are independent counters.
    assert not registry.is_quarantined(QuarantineKind.RESULT_NAMESPACE, "wt_contaminated")


def test_quarantine_is_idempotent_and_keeps_the_first_detection(ledger):
    """A watchdog re-observing the same contamination must not grow the ledger.

    The first detection time is the one that matters (how long contamination went unnoticed),
    so the earliest record wins and the repeat is a no-op returning ``None``.
    """
    registry, clock = ledger
    first = registry.quarantine(
        QuarantineKind.WORKTREE, "wt_stuck",
        reason=QuarantineReason.BUDGET_LEASE_EXPIRED, why="expired",
    )
    clock["now"] += 3600.0
    second = registry.quarantine(
        QuarantineKind.WORKTREE, "wt_stuck",
        reason=QuarantineReason.BUDGET_LEASE_EXPIRED, why="expired again",
    )

    assert first is not None
    assert second is None, "a re-observed contamination must not open a second entry"
    assert len(registry.entries()) == 1
    assert registry.active()[0].detected_at == 1_000_000.0


def test_a_mark_without_an_explanation_is_refused(ledger):
    """An unexplained mark is unreviewable, so ``why`` is required — not defaulted."""
    registry, _clock = ledger
    with pytest.raises(QuarantineFieldError, match="unreviewable"):
        registry.quarantine(
            QuarantineKind.WORKTREE, "wt_x",
            reason=QuarantineReason.MANUAL, why="   ",
        )
    assert registry.active() == []


def test_a_mark_without_an_identity_is_refused(ledger):
    """An empty identity would mark nothing while reading as a successful quarantine."""
    registry, _clock = ledger
    with pytest.raises(QuarantineFieldError, match="identity"):
        registry.quarantine(
            QuarantineKind.WORKTREE, "",
            reason=QuarantineReason.MANUAL, why="operator judgement",
        )


# ── Lifting ──────────────────────────────────────────────────────────────────────────────────


def test_lift_clears_the_quarantine_but_keeps_both_records(ledger):
    """A lift is append-only: the history stays legible, only the *active* set changes."""
    registry, clock = ledger
    registry.quarantine(
        QuarantineKind.WORKTREE, "wt_stuck",
        reason=QuarantineReason.BUDGET_LEASE_EXPIRED, why="expired",
    )
    clock["now"] += 60.0
    lifted = registry.lift(
        QuarantineKind.WORKTREE, "wt_stuck",
        lifted_by="operator", lift_reason="re-run under a valid lease",
    )

    assert lifted is not None and lifted.lifted is True
    assert lifted.lifted_by == "operator"
    assert not registry.is_quarantined(QuarantineKind.WORKTREE, "wt_stuck")
    assert registry.active() == []
    # Both the opening and the lift survive on the ledger.
    assert len(registry.entries()) == 2
    assert [r.lifted for r in registry.entries()] == [False, True]


def test_lifting_something_that_was_never_quarantined_is_a_no_op(ledger):
    """REFUSE direction: a lift must not be able to invent a record."""
    registry, _clock = ledger
    assert registry.lift(
        QuarantineKind.WORKTREE, "wt_never", lifted_by="operator", lift_reason="n/a"
    ) is None
    assert registry.entries() == []


def test_a_lift_must_name_who_lifted_it(ledger):
    """A lift is an accountable act; an anonymous one is refused."""
    registry, _clock = ledger
    registry.quarantine(
        QuarantineKind.WORKTREE, "wt_stuck",
        reason=QuarantineReason.BUDGET_LEASE_EXPIRED, why="expired",
    )
    with pytest.raises(QuarantineFieldError, match="lifted_by"):
        registry.lift(QuarantineKind.WORKTREE, "wt_stuck", lifted_by="", lift_reason="because")
    # …and the quarantine is still standing.
    assert registry.is_quarantined(QuarantineKind.WORKTREE, "wt_stuck")


# ── Fail-closed reads ────────────────────────────────────────────────────────────────────────


def test_a_missing_ledger_is_an_empty_ledger(tmp_path):
    """Absent ≠ corrupt: nothing has ever been quarantined is a legitimate, quiet state."""
    registry = QuarantineRegistry(ledger_path=tmp_path / "never_written.jsonl")
    assert registry.entries() == []
    assert registry.active() == []
    assert not registry.is_quarantined(QuarantineKind.WORKTREE, "wt_any")


def test_a_corrupt_ledger_raises_rather_than_reporting_clean(tmp_path):
    """The fail-closed rule: unknown contamination is never rendered as no contamination."""
    path = tmp_path / "quarantine.jsonl"
    valid = {
        "entry_id": "worktree/a", "kind": "worktree", "identity": "a",
        "reason": "manual", "why": "x", "detected_at": 1.0, "source": "operator",
    }
    path.write_text(json.dumps(valid) + "\nNOT JSON AT ALL\n")
    registry = QuarantineRegistry(ledger_path=path)
    with pytest.raises(QuarantineLedgerError, match="not valid JSON"):
        registry.entries()
    with pytest.raises(QuarantineLedgerError):
        registry.active()


def test_a_record_missing_required_fields_is_refused(tmp_path):
    """A half-parsed record would under-count contamination — so it is a hard error."""
    path = tmp_path / "quarantine.jsonl"
    path.write_text(json.dumps({"entry_id": "worktree/a", "kind": "worktree"}) + "\n")
    with pytest.raises(QuarantineFieldError, match="missing field"):
        QuarantineRegistry(ledger_path=path).entries()


def test_blank_lines_are_skipped_not_treated_as_corruption(tmp_path):
    """A trailing newline is not corruption; only unparseable content is."""
    path = tmp_path / "quarantine.jsonl"
    registry = QuarantineRegistry(ledger_path=path, now_fn=lambda: 1.0)
    registry.quarantine(
        QuarantineKind.WORKTREE, "wt_a", reason=QuarantineReason.MANUAL, why="x"
    )
    path.write_text(path.read_text() + "\n\n")
    assert len(registry.entries()) == 1


# ── The Redis hot path (a mirror, never a dependency) ────────────────────────────────────────


def test_redis_mirrors_the_opening_and_the_lift(ledger):
    """The hot path carries the active hash and the bounded event list."""
    registry, _clock = ledger
    fake = FakeRedis()
    registry._redis = fake  # noqa: SLF001 — exercising the mirror directly is the point

    registry.quarantine(
        QuarantineKind.WORKTREE, "wt_stuck",
        reason=QuarantineReason.BUDGET_LEASE_EXPIRED, why="expired",
    )
    assert "worktree/wt_stuck" in fake.hashes[QUARANTINE_KEY]
    assert len(fake.lists[QUARANTINE_EVENTS_KEY]) == 1

    registry.lift(
        QuarantineKind.WORKTREE, "wt_stuck", lifted_by="operator", lift_reason="cleared"
    )
    assert "worktree/wt_stuck" not in fake.hashes.get(QUARANTINE_KEY, {})
    assert len(fake.lists[QUARANTINE_EVENTS_KEY]) == 2, "the lift is an event too"


def test_a_down_redis_never_costs_the_durable_record(ledger):
    """Durable write first, hot path second — the outage degrades the board, not the ledger."""
    registry, _clock = ledger
    fake = FakeRedis()
    fake.fail_with = ConnectionError("redis is down")
    registry._redis = fake  # noqa: SLF001

    record = registry.quarantine(
        QuarantineKind.WORKTREE, "wt_stuck",
        reason=QuarantineReason.BUDGET_LEASE_EXPIRED, why="expired",
    )
    assert record is not None
    assert registry.is_quarantined(QuarantineKind.WORKTREE, "wt_stuck")
    assert len(registry.ledger_path.read_text().strip().splitlines()) == 1


def test_redis_widens_the_answer_with_identities_the_file_never_saw(ledger):
    """A container that could not write the host filesystem still contributes its quarantine."""
    registry, _clock = ledger
    fake = FakeRedis()
    remote = QuarantineRecord(
        entry_id="worktree/wt_from_container",
        kind=QuarantineKind.WORKTREE,
        identity="wt_from_container",
        reason=QuarantineReason.BUDGET_LEASE_EXPIRED,
        why="expired inside the ladder",
        detected_at=999.0,
        source="lease_watchdog",
    )
    fake.hashes[QUARANTINE_KEY] = {remote.entry_id: json.dumps(remote.to_dict())}
    registry._redis = fake  # noqa: SLF001

    assert registry.active_identities(QuarantineKind.WORKTREE) == {"wt_from_container"}


def test_the_file_wins_over_a_stale_redis_entry(ledger):
    """A hash entry written before a lift must not resurrect the lifted quarantine."""
    registry, clock = ledger
    fake = FakeRedis()
    registry._redis = fake  # noqa: SLF001
    registry.quarantine(
        QuarantineKind.WORKTREE, "wt_stuck",
        reason=QuarantineReason.BUDGET_LEASE_EXPIRED, why="expired",
    )
    clock["now"] += 10.0
    registry.lift(
        QuarantineKind.WORKTREE, "wt_stuck", lifted_by="operator", lift_reason="cleared"
    )
    # Simulate the stale hash field the lift's best-effort hdel failed to remove.
    fake.hashes.setdefault(QUARANTINE_KEY, {})["worktree/wt_stuck"] = json.dumps(
        {
            "entry_id": "worktree/wt_stuck", "kind": "worktree", "identity": "wt_stuck",
            "reason": "budget_lease_expired", "why": "expired", "detected_at": 1_000_000.0,
            "source": "lease_watchdog",
        }
    )
    assert registry.active_identities(QuarantineKind.WORKTREE) == set(), (
        "the authoritative file recorded the lift; a stale mirror must not undo it"
    )


def test_one_corrupt_redis_field_does_not_hide_the_rest(ledger):
    """The hash only widens an already-complete answer, so a bad field is skipped, not fatal."""
    registry, _clock = ledger
    fake = FakeRedis()
    good = QuarantineRecord(
        entry_id="worktree/wt_good", kind=QuarantineKind.WORKTREE, identity="wt_good",
        reason=QuarantineReason.MANUAL, why="x", detected_at=5.0, source="operator",
    )
    fake.hashes[QUARANTINE_KEY] = {
        "worktree/wt_bad": "{not json",
        good.entry_id: json.dumps(good.to_dict()),
    }
    registry._redis = fake  # noqa: SLF001
    assert registry.active_identities(QuarantineKind.WORKTREE) == {"wt_good"}


# ── The consult layer (what analyze / inventory / the snapshot call) ─────────────────────────


def test_filter_excludes_quarantined_paths_and_keeps_clean_ones(ledger):
    """BOTH directions in one test: the contaminated path leaves, the clean paths stay."""
    registry, _clock = ledger
    registry.quarantine(
        QuarantineKind.WORKTREE, "exp_dirty",
        reason=QuarantineReason.BUDGET_LEASE_EXPIRED, why="expired",
    )
    kept, excluded = filter_quarantined_paths(
        ["/tmp/exp_clean_a", "/tmp/exp_dirty", "/tmp/exp_clean_b"], registry=registry
    )
    assert kept == ["/tmp/exp_clean_a", "/tmp/exp_clean_b"]
    assert excluded == ["/tmp/exp_dirty"]


def test_filter_matches_on_name_not_path(ledger):
    """The ledger stores machine-independent names; consumers glob paths. Bridge it here."""
    registry, _clock = ledger
    registry.quarantine(
        QuarantineKind.WORKTREE, "exp_dirty",
        reason=QuarantineReason.MANUAL, why="operator judgement",
    )
    kept, excluded = filter_quarantined_paths(
        ["/some/other/root/exp_dirty"], registry=registry
    )
    assert kept == [] and excluded == ["/some/other/root/exp_dirty"]


def test_filter_excludes_nothing_when_the_ledger_is_empty(tmp_path):
    """REFUSE direction, and the one that matters most: an empty ledger keeps the whole corpus."""
    registry = QuarantineRegistry(ledger_path=tmp_path / "none.jsonl")
    paths = ["/tmp/exp_a", "/tmp/exp_b", "/tmp/exp_c"]
    kept, excluded = filter_quarantined_paths(paths, registry=registry)
    assert kept == paths and excluded == []


def test_a_corrupt_ledger_raises_for_a_publishing_consumer(tmp_path):
    """``on_error="raise"`` — an aggregate built on unknown contamination looks authoritative."""
    path = tmp_path / "quarantine.jsonl"
    path.write_text("garbage\n")
    registry = QuarantineRegistry(ledger_path=path)
    with pytest.raises(QuarantineLedgerError):
        filter_quarantined_paths(["/tmp/exp_a"], registry=registry, on_error="raise")


def test_a_corrupt_ledger_degrades_for_a_display_consumer(tmp_path):
    """``on_error="empty"`` — the game board renders rather than disappearing with the error."""
    path = tmp_path / "quarantine.jsonl"
    path.write_text("garbage\n")
    registry = QuarantineRegistry(ledger_path=path)
    assert quarantined_identities(
        QuarantineKind.WORKTREE, registry=registry, on_error="empty"
    ) == set()


def test_is_worktree_quarantined_reads_by_name(ledger):
    """The one-liner the snapshot and the runner use."""
    registry, _clock = ledger
    registry.quarantine(
        QuarantineKind.WORKTREE, "wt_dirty", reason=QuarantineReason.MANUAL, why="x"
    )
    assert is_worktree_quarantined("wt_dirty", registry=registry)
    assert not is_worktree_quarantined("wt_clean", registry=registry)


# ── The board ────────────────────────────────────────────────────────────────────────────────


def test_the_board_groups_by_kind_and_counts(ledger):
    """The Control Room projection: total and grouped, with every kind present as a key."""
    registry, _clock = ledger
    registry.quarantine(
        QuarantineKind.WORKTREE, "wt_a", reason=QuarantineReason.BUDGET_LEASE_EXPIRED, why="x"
    )
    registry.quarantine(
        QuarantineKind.RESULT_NAMESPACE, "ns_a",
        reason=QuarantineReason.BUDGET_LEASE_EXPIRED, why="x",
    )
    board = quarantine_board(registry)
    assert board["total"] == 2
    assert len(board["kinds"]["worktree"]) == 1
    assert len(board["kinds"]["result_namespace"]) == 1
    assert board["kinds"]["ladder_rung"] == [], "every kind is a key, even when empty"


def test_the_board_shows_a_broken_ledger_rather_than_raising(tmp_path):
    """A dashboard's job is to display the broken state, not vanish with it."""
    path = tmp_path / "quarantine.jsonl"
    path.write_text("garbage\n")
    board = quarantine_board(QuarantineRegistry(ledger_path=path))
    assert "error" in board and board["total"] == 0


# ── Round-tripping ───────────────────────────────────────────────────────────────────────────


def test_a_record_round_trips_through_its_dict(ledger):
    """``to_dict``/``from_dict`` must be lossless or the ledger is not a ledger."""
    registry, _clock = ledger
    original = registry.quarantine(
        QuarantineKind.LADDER_RUNG, "rung-7",
        reason=QuarantineReason.UNKNOWN_COST,
        why="ran with cost_source=unknown",
        source="lease_watchdog",
        run_id="run-9",
        lease_ids=("l1", "l2"),
        cost_source="unknown",
        metadata={"scope": "provider/deepseek"},
    )
    rebuilt = QuarantineRecord.from_dict(original.to_dict())
    assert rebuilt == original
