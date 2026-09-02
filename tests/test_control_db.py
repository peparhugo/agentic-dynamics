"""Control-database tests — the schema, the state machine, and reconstruction.

Driven in BOTH directions, per the repo's testing convention: for every rule the database
states, one test proves it *permits* what it should and one proves it *refuses* what it should
not. A control plane whose database refused everything would pass a naive "is the illegal
transition rejected?" suite while being useless; a control plane that accepted everything would
pass a naive "can I record a run?" suite while being a lie. The negative halves are where the
value is.

Three claims from the ``control_db_publication`` p1 mandate are what these tests exist to
verify, and each has its own section below:

1. **the schema** — the mandated tables, their indexes, and the exact twelve-state vocabulary,
   enforced by the *database* and not only by the Python enum;
2. **immutability** — a run's transitions are recorded, terminal states can never be edited
   (through the API *or* through raw SQL), and gate results carry their ``candidate_sha``;
3. **reconstruction** — a run can be rebuilt from the control db ALONE, which is what demotes
   the run ledger from source of truth to projection.

Storage is real throughout: every test opens an actual SQLite file under ``tmp_path``. There is
nothing to fake — the thing under test *is* the persistence — and a mocked database would prove
the mock's behaviour rather than the schema's. Several tests deliberately reach for the private
``db._conn`` to issue raw SQL: those are the tests asserting that the guarantees survive a
writer who bypasses this module's API entirely, which cannot be shown through the API.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from agentic_dynamics.control.control_db import (
    ALLOWED_TRANSITIONS,
    CONTROL_DB_ENV,
    CONTROL_DB_PATH,
    CONTROL_DB_REL,
    CONTROL_TABLES,
    SCHEMA_VERSION,
    TERMINAL_ATTEMPT_STATES,
    TERMINAL_RUN_STATES,
    AttemptState,
    ControlDB,
    ControlDBError,
    ControlFieldError,
    GateVerdict,
    InvalidTransitionError,
    OutboxStatus,
    ReadOnlyControlDBError,
    RunState,
    TerminalStateError,
    UnknownRunError,
    UnknownStateError,
    attempt_state_from_phase_status,
    resolve_db_path,
    run_state_from_ledger_state,
    summarize_states,
)

#: The exact vocabulary the mandate names, spelled out here as literal strings. Written by hand
#: on purpose: deriving it from the enum under test would make the assertion circular — this
#: list is the *specification*, and it must fail if someone adds a thirteenth state.
MANDATED_RUN_STATES = [
    "queued",
    "running",
    "awaiting_approval",
    "verifying",
    "promotable",
    "promoting",
    "merged",
    "projecting",
    "published",
    "failed",
    "cancelled",
    "quarantined",
]


# ── Fixtures ─────────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def db_path(tmp_path):
    """Path for a per-test database. Never the repo's real control.db."""
    return tmp_path / "control" / "control.db"


@pytest.fixture()
def db(db_path):
    """An open writer handle on a fresh database."""
    handle = ControlDB.open(db_path)
    yield handle
    handle.close()


def make_run(db: ControlDB, **overrides) -> str:
    """Create a run with sane defaults and return its id (test noise reducer)."""
    fields = {
        "spec_name": "control_db_publication",
        "workflow_revision_id": "sha256:1d1c6a10ab5e",
        "candidate_sha": "a" * 40,
        "model": "anthropic/claude-opus-5",
    }
    fields.update(overrides)
    return db.create_run(**fields).run_id


def advance(db: ControlDB, run_id: str, *states: str) -> None:
    """Walk a run through a sequence of states, one recorded transition each."""
    for state in states:
        db.transition_run(run_id, state)


# ── 1. Schema ────────────────────────────────────────────────────────────────────────────────


def test_every_mandated_table_exists(db):
    """The seven mandated tables (plus the transition log and meta) are created on open."""
    rows = db._conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    present = {row["name"] for row in rows}
    for table in CONTROL_TABLES:
        assert table in present, f"missing table {table}"
    # The mandate's own list, spelled out rather than taken from the module's constant — the
    # constant is what's under test.
    for mandated in (
        "runs",
        "step_attempts",
        "gate_results",
        "approvals",
        "promotions",
        "outbox",
        "projection_watermarks",
    ):
        assert mandated in present


def test_mandated_columns_are_present_on_every_table(db):
    """Each table carries exactly the columns the mandate names (extras are allowed, gaps not)."""
    expected = {
        "runs": {"run_id", "spec_name", "workflow_revision_id", "candidate_sha", "state",
                 "model", "started_at", "ended_at", "ledger_path", "cost_usd"},
        "step_attempts": {"attempt_id", "run_id", "step_id", "attempt_no", "model", "state",
                          "started_at", "ended_at", "tokens", "cost_usd", "exit_code", "error"},
        "gate_results": {"gate_id", "run_id", "step_id", "verdict", "evidence_json", "executor",
                         "candidate_sha", "started_at", "ended_at"},
        "approvals": {"approval_id", "run_id", "gate_id", "candidate_sha", "operator",
                      "decided_at", "artifact_path"},
        "promotions": {"run_id", "candidate_sha", "base_sha", "squash_sha", "pushed_at", "by"},
        "outbox": {"event_id", "run_id", "payload_json", "status", "attempts", "next_retry_at",
                   "created_at"},
        "projection_watermarks": {"projection", "last_event_id", "source_head_event_id",
                                  "lag_events", "last_success_at", "last_error"},
    }
    for table, columns in expected.items():
        found = {row["name"] for row in db._conn.execute(f"PRAGMA table_info({table})")}
        assert columns <= found, f"{table} is missing {columns - found}"


def test_the_expected_indexes_exist(db):
    """Query paths the control packet and the publication gate depend on are indexed."""
    rows = db._conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()
    present = {row["name"] for row in rows}
    for index in (
        "idx_runs_state",                    # "what is in flight?"
        "idx_runs_candidate_sha",            # "what happened to this tree?"
        "idx_step_attempts_run",             # run reconstruction
        "uq_step_attempts_run_step_no",      # the retry contract
        "idx_gate_results_run",
        "idx_gate_results_candidate_sha",    # "what has been proven about this sha?"
        "idx_approvals_run",
        "idx_promotions_candidate_sha",
        "idx_outbox_status",                 # the publisher's poll
        "idx_run_transitions_run",
    ):
        assert index in present, f"missing index {index}"


def test_run_state_vocabulary_is_exactly_the_mandated_twelve():
    """No thirteenth state, no missing state, and the wire strings match the mandate."""
    assert [state.value for state in RunState] == MANDATED_RUN_STATES
    # No "completed"/"done"/"ok" — the overload the vocabulary exists to delete.
    assert "completed" not in MANDATED_RUN_STATES
    assert "done" not in MANDATED_RUN_STATES
    assert "ok" not in MANDATED_RUN_STATES


def test_terminal_states_are_the_four_outcomes():
    """``merged`` is deliberately NOT terminal: merged work still has to be projected."""
    assert {s.value for s in TERMINAL_RUN_STATES} == {
        "published", "failed", "cancelled", "quarantined"
    }
    assert RunState.MERGED not in TERMINAL_RUN_STATES
    assert RunState.PROJECTING not in TERMINAL_RUN_STATES


def test_terminal_states_have_no_outgoing_edges():
    """Terminality is a property of the transition graph, not only of a check in Python."""
    for state in TERMINAL_RUN_STATES:
        assert ALLOWED_TRANSITIONS[state] == frozenset()


def test_state_is_stored_as_a_string_never_a_bool(db):
    """The mandate's 'the db stores the state string, never a bool overload'."""
    run_id = make_run(db)
    row = db._conn.execute("SELECT state FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    assert isinstance(row["state"], str)
    assert row["state"] == "queued"
    # And no bool-shaped success column sneaked into the schema.
    columns = {r["name"] for r in db._conn.execute("PRAGMA table_info(runs)")}
    assert not columns & {"ok", "completed", "success", "done"}


def test_database_itself_refuses_a_state_outside_the_vocabulary(db):
    """A CHECK constraint, not just the Python enum — raw SQL cannot mint a new state."""
    with pytest.raises(sqlite3.IntegrityError):
        db._conn.execute(
            "INSERT INTO runs (run_id, spec_name, state) VALUES ('r1', 'spec', 'completed')"
        )


def test_api_refuses_a_state_outside_the_vocabulary(db):
    """And the API refuses it earlier, with a message that names the whole vocabulary."""
    run_id = make_run(db)
    with pytest.raises(UnknownStateError) as excinfo:
        db.transition_run(run_id, "completed")
    assert "queued" in str(excinfo.value) and "quarantined" in str(excinfo.value)


def test_schema_version_and_epoch_are_seeded(db):
    """A fresh database knows its own version and starts its epoch at zero."""
    assert db.schema_version() == SCHEMA_VERSION
    assert db.control_epoch() == 0


def test_reopening_an_existing_database_is_idempotent(db_path):
    """The orchestrator opens this file on every run; a second open must not disturb it."""
    with ControlDB.open(db_path) as first:
        run_id = make_run(first)
    with ControlDB.open(db_path) as second:
        assert second.get_run(run_id) is not None
        assert second.schema_version() == SCHEMA_VERSION


def test_a_newer_schema_version_is_refused(db_path):
    """Half-understanding the control state is worse than stopping."""
    with ControlDB.open(db_path) as handle:
        handle._conn.execute(
            "UPDATE control_meta SET value = ? WHERE key = 'schema_version'",
            (str(SCHEMA_VERSION + 1),),
        )
    with pytest.raises(ControlDBError, match="schema version"):
        ControlDB.open(db_path)


def test_a_v3_database_is_migrated_in_place_to_v4(db_path):
    """A pre-g1 (v3) database gains the family-link columns on the next writer open."""
    # Build a genuine v3 database: the runs table WITHOUT parent_run_id / family_id, at
    # schema_version 3, with a legacy row already present.
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE control_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO control_meta(key, value) VALUES ('schema_version', '3');
            INSERT INTO control_meta(key, value) VALUES ('control_epoch', '0');
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY, spec_name TEXT NOT NULL,
                workflow_revision_id TEXT NOT NULL DEFAULT '', candidate_sha TEXT NOT NULL DEFAULT '',
                state TEXT NOT NULL, model TEXT NOT NULL DEFAULT '', started_at TEXT NOT NULL DEFAULT '',
                ended_at TEXT NOT NULL DEFAULT '', ledger_path TEXT NOT NULL DEFAULT '',
                cost_usd REAL NOT NULL DEFAULT 0.0
            );
            CREATE TABLE run_transitions (
                transition_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                from_state TEXT, to_state TEXT NOT NULL, at TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '', actor TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO runs (run_id, spec_name, state)
            VALUES ('legacy-run', 'old_spec', 'failed');
            """
        )
        conn.commit()
    finally:
        conn.close()

    with ControlDB.open(db_path) as handle:
        run = handle.get_run("legacy-run")
        assert run.parent_run_id == ""
        assert run.family_id == ""  # a pre-g1 run is its own family
        assert handle.schema_version() == SCHEMA_VERSION

    # A fresh child can now link to the legacy row (the legacy row becomes the family root).
    with ControlDB.open(db_path) as handle:
        child = handle.create_run(
            spec_name="old_spec", model="m", state="running", parent_run_id="legacy-run"
        )
        assert child.parent_run_id == "legacy-run"
        assert child.family_id == "legacy-run"
        # Re-opening is idempotent — no duplicate columns.
        assert handle.schema_version() == SCHEMA_VERSION


# ── Path resolution ──────────────────────────────────────────────────────────────────────────


def test_default_path_is_the_mandated_location():
    """``experiments/results/control/control.db``, repo-root relative."""
    assert CONTROL_DB_REL == "experiments/results/control/control.db"
    assert str(CONTROL_DB_PATH).endswith("experiments/results/control/control.db")


def test_resolve_db_path_precedence(tmp_path, monkeypatch):
    """Explicit argument beats the environment beats the default."""
    monkeypatch.setenv(CONTROL_DB_ENV, str(tmp_path / "from_env.db"))
    assert resolve_db_path(tmp_path / "explicit.db").name == "explicit.db"
    assert resolve_db_path().name == "from_env.db"
    monkeypatch.delenv(CONTROL_DB_ENV)
    assert resolve_db_path() == CONTROL_DB_PATH


# ── 2. Lifecycle + immutability ──────────────────────────────────────────────────────────────


def test_the_full_happy_path_is_recorded_in_order(db):
    """queued → running → verifying → promotable → promoting → merged → projecting → published."""
    run_id = make_run(db)
    advance(db, run_id, "running", "verifying", "promotable", "promoting", "merged",
            "projecting", "published")
    reconstructed = db.reconstruct_run(run_id)
    assert reconstructed.state_path == [
        "queued", "running", "verifying", "promotable", "promoting", "merged",
        "projecting", "published",
    ]
    assert reconstructed.run.state is RunState.PUBLISHED


def test_the_failure_path_is_recorded(db):
    """A run can fail from anywhere, and the history keeps where it failed from."""
    run_id = make_run(db)
    advance(db, run_id, "running")
    db.transition_run(run_id, "failed", reason="p1 exited 1")
    transitions = db.transitions(run_id)
    assert transitions[-1].from_state is RunState.RUNNING
    assert transitions[-1].to_state is RunState.FAILED
    assert transitions[-1].reason == "p1 exited 1"


def test_the_cancelled_path_is_recorded(db):
    """A queued run can be cancelled before any work happens."""
    run_id = make_run(db)
    record = db.transition_run(run_id, "cancelled", reason="operator")
    assert record.state is RunState.CANCELLED
    assert record.is_terminal


def test_a_run_may_only_be_created_in_queued_or_running(db):
    """An outcome with no recorded path to it is an assertion, not evidence."""
    assert db.create_run(spec_name="s", state="running").state is RunState.RUNNING
    with pytest.raises(InvalidTransitionError):
        db.create_run(spec_name="s", state="merged")
    with pytest.raises(InvalidTransitionError):
        db.create_run(spec_name="s", state="published")


def test_an_illegal_transition_is_refused(db):
    """No skipping the lifecycle: queued cannot jump to merged."""
    run_id = make_run(db)
    with pytest.raises(InvalidTransitionError) as excinfo:
        db.transition_run(run_id, "merged")
    assert "queued → merged" in str(excinfo.value)
    # And the refusal left nothing behind — no partial state, no phantom transition.
    assert db.get_run(run_id).state is RunState.QUEUED
    assert len(db.transitions(run_id)) == 1


def test_cancelling_after_merge_is_refused_but_failing_is_not(db):
    """Once work is on main, 'cancelled' is a lie; 'failed'/'quarantined' remain honest."""
    run_id = make_run(db)
    advance(db, run_id, "running", "promotable", "promoting", "merged")
    with pytest.raises(InvalidTransitionError):
        db.transition_run(run_id, "cancelled")
    assert db.transition_run(run_id, "quarantined").state is RunState.QUARANTINED


def test_failed_and_quarantined_are_reachable_from_every_non_terminal_state():
    """Anything can break, and anything can turn out to be unaccounted-for."""
    for state, targets in ALLOWED_TRANSITIONS.items():
        if state in TERMINAL_RUN_STATES:
            continue
        assert RunState.FAILED in targets, state
        assert RunState.QUARANTINED in targets, state


def test_a_terminal_run_refuses_every_further_transition(db):
    """The mandate's 'an update of a terminal state is refused'."""
    run_id = make_run(db)
    advance(db, run_id, "running", "failed")
    for target in ("running", "promotable", "published", "cancelled"):
        with pytest.raises(TerminalStateError):
            db.transition_run(run_id, target)


def test_a_terminal_run_refuses_metadata_edits_too(db):
    """Immutable means the whole row, not only the state column."""
    run_id = make_run(db)
    advance(db, run_id, "running", "failed")
    with pytest.raises(TerminalStateError):
        db.update_run(run_id, ledger_path="/tmp/after-the-fact.json")


def test_terminal_immutability_survives_raw_sql(db):
    """The guarantee is in the schema, so a writer who bypasses this API still cannot edit."""
    run_id = make_run(db)
    advance(db, run_id, "running", "verifying", "promotable", "promoting", "merged",
            "projecting", "published")
    with pytest.raises(sqlite3.IntegrityError, match="terminal"):
        db._conn.execute("UPDATE runs SET state = 'running' WHERE run_id = ?", (run_id,))
    with pytest.raises(sqlite3.IntegrityError, match="terminal"):
        db._conn.execute("UPDATE runs SET cost_usd = 999.0 WHERE run_id = ?", (run_id,))


def test_a_non_terminal_run_can_still_be_updated(db):
    """The negative half: immutability must not freeze runs that are still in flight."""
    run_id = make_run(db)
    advance(db, run_id, "running")
    updated = db.update_run(run_id, candidate_sha="b" * 40, ledger_path="/tmp/run.json",
                            cost_usd=1.25)
    assert updated.candidate_sha == "b" * 40
    assert updated.ledger_path == "/tmp/run.json"
    assert updated.cost_usd == 1.25


def test_runs_are_never_deleted(db):
    """A control plane that can forget a run has not recorded it."""
    run_id = make_run(db)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db._conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))


def test_the_transition_log_is_append_only(db):
    """History that can be rewritten is not history."""
    run_id = make_run(db)
    advance(db, run_id, "running")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db._conn.execute("UPDATE run_transitions SET to_state = 'merged' WHERE run_id = ?",
                         (run_id,))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db._conn.execute("DELETE FROM run_transitions WHERE run_id = ?", (run_id,))


def test_the_terminal_transition_stamps_ended_at_and_the_final_cost(db):
    """The last writable moment: a terminal transition carries the run's final numbers."""
    run_id = make_run(db)
    advance(db, run_id, "running")
    final = db.transition_run(run_id, "failed", cost_usd=3.5, ledger_path="/tmp/run.json")
    assert final.ended_at, "a terminal run must record when it ended"
    assert final.cost_usd == 3.5
    assert final.ledger_path == "/tmp/run.json"


def test_a_non_terminal_transition_does_not_stamp_ended_at(db):
    """The negative half: an in-flight run has no end time."""
    run_id = make_run(db)
    assert db.transition_run(run_id, "running").ended_at == ""


def test_transitioning_an_unknown_run_is_refused(db):
    """A transition addressed to nothing must not silently create a run."""
    with pytest.raises(UnknownRunError):
        db.transition_run("run-does-not-exist", "running")
    assert db.runs() == []


def test_control_epoch_advances_on_every_transition_and_not_on_reads(db):
    """p4's turn-diffing depends on this counter moving exactly when the state does."""
    start = db.control_epoch()
    run_id = make_run(db)
    after_create = db.control_epoch()
    assert after_create == start + 1
    db.transition_run(run_id, "running")
    assert db.control_epoch() == after_create + 1
    # Reads do not move it, or an observer could never tell "nothing changed" from "I looked".
    db.runs()
    db.reconstruct_run(run_id)
    assert db.control_epoch() == after_create + 1


def test_control_epoch_advances_on_attempt_start_and_finish(db):
    """e4: the epoch sees PHASE progress — a step attempt's start AND end are durable changes.

    The whole point of the per-phase bump: an 8-phase run moves the epoch 16 times while it
    executes, so a master diffing turn-to-turn packets sees the work actually happening, not
    only the run's two top-level transitions (create → running → promotable).
    """
    run_id = make_run(db)
    base = db.control_epoch()  # after create_run's own bump

    first = db.start_attempt(run_id, step_id="p1", model="m")
    assert db.control_epoch() == base + 1  # the attempt START is itself a durable state change

    db.finish_attempt(first.attempt_id, AttemptState.OK)
    assert db.control_epoch() == base + 2  # ... and so is its OUTCOME

    # Reads still do not move it — the per-phase bump must not make observation an event.
    db.attempts(run_id)
    db.transitions(run_id)
    assert db.control_epoch() == base + 2

    # A second phase bumps twice more: 2 phases = 4 phase-level changes, end to end.
    second = db.start_attempt(run_id, step_id="p2", model="m")
    assert db.control_epoch() == base + 3
    db.finish_attempt(second.attempt_id, AttemptState.OK)
    assert db.control_epoch() == base + 4


def test_runs_can_be_filtered_by_state_and_spec(db):
    """The control packet's queries: what is in flight, what is awaiting, what failed."""
    first = make_run(db, spec_name="alpha")
    second = make_run(db, spec_name="beta")
    advance(db, first, "running")
    advance(db, second, "running", "awaiting_approval")
    assert [r.run_id for r in db.runs(state=RunState.AWAITING_APPROVAL)] == [second]
    assert {r.run_id for r in db.runs(states=["running", "awaiting_approval"])} == {first, second}
    assert [r.run_id for r in db.runs(spec_name="alpha")] == [first]


# ── g1: the split-run family link (parent_run_id / family_id) ───────────────────────────────


def test_a_fresh_run_is_its_own_family_root(db):
    """A run with no parent is a family root: family_id == its own run_id (g1, F5)."""
    run = db.create_run(spec_name="g1_split", model="m")
    assert run.parent_run_id == ""
    assert run.family_id == run.run_id


def test_a_child_inherits_the_parents_family(db):
    """A --resume continuation records its parent and inherits the family id (g1, F5)."""
    parent = db.create_run(spec_name="g1_split", model="m", state=RunState.RUNNING)
    db.transition_run(parent.run_id, RunState.FAILED, reason="w2 timeout")
    child = db.create_run(
        spec_name="g1_split",
        model="m",
        state=RunState.RUNNING,
        parent_run_id=parent.run_id,
    )
    assert child.parent_run_id == parent.run_id
    assert child.family_id == parent.family_id == parent.run_id
    # Round trip: get_run returns the link.
    fetched = db.get_run(child.run_id)
    assert (fetched.parent_run_id, fetched.family_id) == (parent.run_id, parent.run_id)


def test_a_child_of_a_pre_g1_parent_makes_the_parent_the_root(db):
    """A parent row with no family id (a pre-g1 run, stored before the column existed)
    becomes the root for its child."""
    # Simulate a legacy row: the family columns predate it, so they are ''.
    db._conn.execute(
        "INSERT INTO runs (run_id, spec_name, workflow_revision_id, candidate_sha, state,"
        " model, started_at, ended_at, ledger_path, cost_usd, parent_run_id, family_id)"
        " VALUES ('legacy-parent', 'g1_split', '', '', 'failed', 'm',"
        " '2026-09-02T10:00:00Z', '2026-09-02T11:00:00Z', '', 0.0, '', '')"
    )
    db._conn.execute(
        "INSERT INTO run_transitions (run_id, from_state, to_state, at, reason, actor)"
        " VALUES ('legacy-parent', NULL, 'failed', '2026-09-02T11:00:00Z', '', 'orchestrator')"
    )
    child = db.create_run(spec_name="g1_split", model="m", state=RunState.RUNNING,
                          parent_run_id="legacy-parent")
    assert child.family_id == "legacy-parent"


def test_runs_can_be_grouped_by_family(db):
    """runs() filters surface the family grouping (a family + an unrelated attempt)."""
    parent = db.create_run(spec_name="g1_split", model="m", state=RunState.RUNNING)
    child = db.create_run(spec_name="g1_split", model="m", state=RunState.RUNNING,
                          parent_run_id=parent.run_id)
    other = db.create_run(spec_name="g1_split", model="m", state=RunState.RUNNING)
    family_ids = {r.run_id: r.family_id for r in db.runs(spec_name="g1_split")}
    assert family_ids[parent.run_id] == family_ids[child.run_id] == parent.run_id
    # The genuinely-new attempt is its own family.
    assert family_ids[other.run_id] == other.run_id
    assert len({family_ids[r] for r in (parent.run_id, child.run_id, other.run_id)}) == 2


# ── Step attempts ────────────────────────────────────────────────────────────────────────────


def test_attempt_numbers_increment_per_step(db):
    """A retry is a new row, never an overwrite — that is what makes retry rate measurable."""
    run_id = make_run(db)
    first = db.start_attempt(run_id, step_id="p1", model="m")
    db.finish_attempt(first.attempt_id, AttemptState.FAILED, error="boom", exit_code=1)
    second = db.start_attempt(run_id, step_id="p1", model="m")
    assert (first.attempt_no, second.attempt_no) == (1, 2)
    # A different step starts its own numbering.
    assert db.start_attempt(run_id, step_id="p2", model="m").attempt_no == 1


def test_duplicate_attempt_numbers_are_refused_by_the_schema(db):
    """The UNIQUE index is the retry contract; it must not be bypassable."""
    run_id = make_run(db)
    db.start_attempt(run_id, step_id="p1", attempt_no=1)
    with pytest.raises(sqlite3.IntegrityError):
        db.start_attempt(run_id, step_id="p1", attempt_no=1)


def test_a_finished_attempt_cannot_be_finished_again(db):
    """The first recorded outcome of an invocation is the outcome."""
    run_id = make_run(db)
    attempt = db.start_attempt(run_id, step_id="p1")
    db.finish_attempt(attempt.attempt_id, AttemptState.OK, tokens=10, cost_usd=0.1, exit_code=0)
    with pytest.raises(TerminalStateError):
        db.finish_attempt(attempt.attempt_id, AttemptState.FAILED)


def test_a_running_attempt_can_still_be_finished(db):
    """The negative half: only TERMINAL attempts are frozen."""
    run_id = make_run(db)
    attempt = db.start_attempt(run_id, step_id="p1")
    assert attempt.state is AttemptState.RUNNING
    assert not attempt.is_terminal
    assert db.finish_attempt(attempt.attempt_id, AttemptState.OK).state is AttemptState.OK


def test_awaiting_is_a_terminal_attempt_state_but_not_a_failure(db):
    """A checkpoint stop is a designed outcome — the P1 awaiting-approval distinction."""
    assert AttemptState.AWAITING in TERMINAL_ATTEMPT_STATES
    run_id = make_run(db)
    attempt = db.start_attempt(run_id, step_id="checkpoint")
    finished = db.finish_attempt(attempt.attempt_id, AttemptState.AWAITING)
    assert finished.state is AttemptState.AWAITING
    assert finished.error == ""


def test_an_unobserved_exit_code_stays_null_and_never_becomes_zero(db):
    """0 means 'clean exit'. An absent exit code must not be readable as success."""
    run_id = make_run(db)
    attempt = db.start_attempt(run_id, step_id="p1")
    finished = db.finish_attempt(attempt.attempt_id, AttemptState.FAILED, error="timeout")
    assert finished.exit_code is None
    other = db.start_attempt(run_id, step_id="p2")
    assert db.finish_attempt(other.attempt_id, AttemptState.OK, exit_code=0).exit_code == 0


def test_an_attempt_for_an_unknown_run_is_refused(db):
    """Foreign keys are ON: orphan attempts are the exact state this database deletes."""
    with pytest.raises(UnknownRunError):
        db.start_attempt("run-nope", step_id="p1")


def test_an_unknown_attempt_state_is_refused(db):
    """The attempt vocabulary is closed too."""
    run_id = make_run(db)
    attempt = db.start_attempt(run_id, step_id="p1")
    with pytest.raises(UnknownStateError):
        db.finish_attempt(attempt.attempt_id, "mostly-fine")


# ── Gate results ─────────────────────────────────────────────────────────────────────────────


def test_a_gate_result_carries_its_candidate_sha(db):
    """The mandate: 'gate results carry their candidate_sha'."""
    run_id = make_run(db)
    gate = db.record_gate_result(
        run_id,
        step_id="p8_test_gate",
        verdict=GateVerdict.PASS,
        candidate_sha="c" * 40,
        evidence={"tests_passed": 42, "tests_total": 42},
        executor="pytest",
    )
    assert gate.candidate_sha == "c" * 40
    assert gate.evidence == {"tests_passed": 42, "tests_total": 42}
    assert json.loads(gate.evidence_json)["tests_total"] == 42


def test_a_gate_result_without_a_candidate_sha_is_refused(db):
    """A verdict about an unnamed tree is how a stale PASS authorises the wrong promotion."""
    run_id = make_run(db)
    with pytest.raises(ControlFieldError, match="candidate_sha"):
        db.record_gate_result(run_id, step_id="p8", verdict="pass", candidate_sha="")
    with pytest.raises(ControlFieldError, match="candidate_sha"):
        db.record_gate_result(run_id, step_id="p8", verdict="pass", candidate_sha="   ")
    assert db.gate_results(run_id) == []


def test_the_schema_also_refuses_an_empty_candidate_sha(db):
    """Enforced beneath the API, so raw SQL cannot record a verdict about nothing."""
    run_id = make_run(db)
    with pytest.raises(sqlite3.IntegrityError):
        db._conn.execute(
            "INSERT INTO gate_results (gate_id, run_id, step_id, verdict, candidate_sha) "
            "VALUES ('g1', ?, 'p8', 'pass', '')",
            (run_id,),
        )


def test_gate_results_are_append_only(db):
    """Evidence that can be edited after the fact is not evidence."""
    run_id = make_run(db)
    gate = db.record_gate_result(run_id, step_id="p8", verdict="fail", candidate_sha="d" * 40)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db._conn.execute("UPDATE gate_results SET verdict = 'pass' WHERE gate_id = ?",
                         (gate.gate_id,))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db._conn.execute("DELETE FROM gate_results WHERE gate_id = ?", (gate.gate_id,))


def test_gate_results_are_queryable_by_candidate_sha(db):
    """The publication gate's question: what has been proven about THIS tree?"""
    run_id = make_run(db)
    db.record_gate_result(run_id, step_id="p8", verdict="pass", candidate_sha="e" * 40)
    db.record_gate_result(run_id, step_id="p7", verdict="fail", candidate_sha="f" * 40)
    assert [g.step_id for g in db.gate_results(candidate_sha="e" * 40)] == ["p8"]
    assert [g.step_id for g in db.gate_results(run_id, verdict=GateVerdict.FAIL)] == ["p7"]


def test_error_is_a_distinct_verdict_from_fail(db):
    """'the gate could not run' is not evidence about the work."""
    run_id = make_run(db)
    gate = db.record_gate_result(run_id, step_id="p7", verdict=GateVerdict.ERROR,
                                 candidate_sha="e" * 40, executor="deepseek/deepseek-v4-flash")
    assert gate.verdict is GateVerdict.ERROR
    assert gate.verdict is not GateVerdict.FAIL


def test_an_unknown_verdict_is_refused(db):
    run_id = make_run(db)
    with pytest.raises(UnknownStateError):
        db.record_gate_result(run_id, step_id="p8", verdict="probably-fine",
                              candidate_sha="e" * 40)


# ── Approvals and promotions ─────────────────────────────────────────────────────────────────


def test_an_approval_records_its_operator_gate_and_sha(db):
    """An approval with no approver is not an approval."""
    run_id = make_run(db)
    gate = db.record_gate_result(run_id, step_id="checkpoint", verdict=GateVerdict.WAIVED,
                                 candidate_sha="a" * 40, executor="operator")
    approval = db.record_approval(run_id, gate_id=gate.gate_id, candidate_sha="a" * 40,
                                  operator="controller", artifact_path="docs/decision.md")
    assert (approval.operator, approval.gate_id) == ("controller", gate.gate_id)
    assert db.approvals(run_id) == [approval]


def test_an_approval_without_an_operator_or_sha_is_refused(db):
    run_id = make_run(db)
    with pytest.raises(ControlFieldError, match="operator"):
        db.record_approval(run_id, candidate_sha="a" * 40, operator="")
    with pytest.raises(ControlFieldError, match="candidate_sha"):
        db.record_approval(run_id, candidate_sha="", operator="controller")


def test_a_promotion_is_recorded_once_per_candidate_sha(db):
    """Duplicate promotion rows would misreport how many times work reached main."""
    run_id = make_run(db)
    promotion = db.record_promotion(run_id, candidate_sha="a" * 40, base_sha="b" * 40,
                                    squash_sha="c" * 40, by="promote.py")
    assert promotion.squash_sha == "c" * 40
    assert promotion.by == "promote.py"
    with pytest.raises(sqlite3.IntegrityError):
        db.record_promotion(run_id, candidate_sha="a" * 40)
    # A different (corrected) sha may still be promoted — the negative half.
    assert db.record_promotion(run_id, candidate_sha="d" * 40).candidate_sha == "d" * 40


def test_promotions_and_approvals_are_append_only(db):
    run_id = make_run(db)
    db.record_promotion(run_id, candidate_sha="a" * 40)
    db.record_approval(run_id, candidate_sha="a" * 40, operator="controller")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db._conn.execute("UPDATE promotions SET base_sha = 'x' WHERE run_id = ?", (run_id,))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db._conn.execute("DELETE FROM approvals WHERE run_id = ?", (run_id,))


# ── Outbox (storage primitives) ──────────────────────────────────────────────────────────────


def test_an_outbox_row_starts_pending_and_flips_to_delivered(db):
    """Delivery is marked only after an ack — the ordering that makes it at-least-once."""
    run_id = make_run(db)
    event = db.enqueue_outbox_event(run_id, {"schema": "workflow-fact/v1", "run": run_id})
    assert event.status is OutboxStatus.PENDING
    assert event.payload["schema"] == "workflow-fact/v1"
    delivered = db.mark_outbox_delivered(event.event_id)
    assert delivered.status is OutboxStatus.DELIVERED
    assert delivered.delivered_at and delivered.attempts == 1


def test_a_retry_bumps_attempts_and_defers_the_row(db):
    """Backoff is expressed as data; the policy that sets it belongs to the publisher (p2)."""
    run_id = make_run(db)
    event = db.enqueue_outbox_event(run_id, {"n": 1})
    retried = db.mark_outbox_retry(event.event_id, next_retry_at="2099-01-01T00:00:00Z",
                                   error="stream unreachable")
    assert (retried.attempts, retried.status) == (1, OutboxStatus.PENDING)
    assert retried.last_error == "stream unreachable"
    # Deferred: not eligible now...
    assert db.pending_outbox_events(now="2026-09-02T00:00:00Z") == []
    # ...but eligible once its time comes.
    assert [e.event_id for e in db.pending_outbox_events(now="2099-06-01T00:00:00Z")] == [
        event.event_id
    ]


def test_a_dead_row_stays_visible(db):
    """An undelivered knowledge event is a gap in the projection chain; it must be findable."""
    run_id = make_run(db)
    event = db.enqueue_outbox_event(run_id, {"n": 1})
    dead = db.mark_outbox_dead(event.event_id, error="cap reached")
    assert dead.status is OutboxStatus.DEAD
    assert dead.last_error == "cap reached"
    assert [e.event_id for e in db.outbox_events(status=OutboxStatus.DEAD)] == [event.event_id]
    assert db.pending_outbox_events() == []


def test_a_delivered_row_cannot_be_re_marked(db):
    """Re-marking would hide a double-delivery bug instead of surfacing it."""
    run_id = make_run(db)
    event = db.enqueue_outbox_event(run_id, {"n": 1})
    db.mark_outbox_delivered(event.event_id)
    with pytest.raises(TerminalStateError):
        db.mark_outbox_delivered(event.event_id)
    with pytest.raises(TerminalStateError):
        db.mark_outbox_retry(event.event_id, next_retry_at="")


def test_the_transition_and_its_outbox_events_commit_or_roll_back_together(db):
    """The outbox guarantee: no state moves without its events, and vice versa.

    This is the atomicity p2's parent write depends on — proven here at the storage level so
    that phase can rely on composing these calls inside one :meth:`ControlDB.transaction`.
    """
    run_id = make_run(db)
    advance(db, run_id, "running")

    class CrashError(RuntimeError):
        """Stands in for a process dying between the two writes."""

    with pytest.raises(CrashError), db.transaction():
        db.transition_run(run_id, "verifying")
        db.enqueue_outbox_event(run_id, {"schema": "workflow-fact/v1"})
        raise CrashError("crash between the two writes")

    # Neither half survived: the state did not move and no event was queued.
    assert db.get_run(run_id).state is RunState.RUNNING
    assert db.outbox_events(run_id=run_id) == []
    assert [t.to_state.value for t in db.transitions(run_id)] == ["queued", "running"]

    # And the positive half: the same composition, without the crash, commits both.
    with db.transaction():
        db.transition_run(run_id, "verifying")
        db.enqueue_outbox_event(run_id, {"schema": "workflow-fact/v1"})
    assert db.get_run(run_id).state is RunState.VERIFYING
    assert len(db.outbox_events(run_id=run_id)) == 1


# ── Projection watermarks (storage primitives) ───────────────────────────────────────────────


def test_a_watermark_round_trips_with_its_lag(db):
    db.record_watermark("registry", last_event_id="1725-0", source_head_event_id="1725-0",
                        lag_events=0)
    db.record_watermark("chroma", last_event_id="1700-0", source_head_event_id="1725-0",
                        lag_events=3)
    assert db.get_watermark("chroma").lag_events == 3
    assert [w.projection for w in db.watermarks()] == ["chroma", "registry"]


def test_unknown_lag_is_recorded_as_unknown_not_as_zero(db):
    """A fabricated 0 would read as 'fully caught up' — the worst wrong answer here."""
    watermark = db.record_watermark("neo4j", last_event_id="1700-0")
    assert watermark.lag_events is None


def test_a_failed_poll_does_not_refresh_the_success_stamp(db):
    """A stale projector must AGE visibly rather than look healthy forever."""
    fresh = db.record_watermark("registry", last_event_id="10-0", lag_events=0)
    assert fresh.last_success_at
    failed = db.record_watermark("registry", last_event_id="10-0", lag_events=5,
                                 last_error="redis unreachable")
    assert failed.last_error == "redis unreachable"
    assert failed.last_success_at == fresh.last_success_at, "a failure must not look like success"
    assert failed.lag_events == 5


def test_a_projection_that_never_reported_is_absent_not_zero(db):
    """Absent and caught-up are different states, and stay different."""
    assert db.get_watermark("chroma") is None


def test_a_watermark_requires_a_projection_name(db):
    with pytest.raises(ControlFieldError, match="projection"):
        db.record_watermark("")


# ── 3. Reconstruction ────────────────────────────────────────────────────────────────────────


def test_a_run_is_fully_reconstructible_from_the_database_alone(db_path):
    """The mandate's central proof: the ledger becomes a projection, not the source.

    A complete run is written, the handle is CLOSED (so nothing is held in memory), and the
    database is reopened READ-ONLY — the posture every non-orchestrator consumer uses. Every
    fact about the run then comes back out of the file: its identity, its lifecycle path, its
    attempts with costs and exit codes, its gate verdicts with their candidate shas, its
    approval, and its promotion. No ledger JSON, no Redis, no spec index, no git.
    """
    with ControlDB.open(db_path) as writer:
        run_id = make_run(writer)
        writer.transition_run(run_id, "running")

        first = writer.start_attempt(run_id, step_id="p1_control_db", model="opus")
        writer.finish_attempt(first.attempt_id, AttemptState.FAILED, tokens=100, cost_usd=0.5,
                              exit_code=1, error="pytest failed")
        second = writer.start_attempt(run_id, step_id="p1_control_db", model="opus")
        writer.finish_attempt(second.attempt_id, AttemptState.OK, tokens=200, cost_usd=1.5,
                              exit_code=0)

        writer.transition_run(run_id, "verifying")
        writer.record_gate_result(run_id, step_id="p8_test_gate", verdict=GateVerdict.PASS,
                                  candidate_sha="a" * 40, executor="pytest",
                                  evidence={"tests_passed": 10})
        writer.transition_run(run_id, "awaiting_approval")
        writer.record_approval(run_id, candidate_sha="a" * 40, operator="controller")
        writer.transition_run(run_id, "verifying")
        writer.transition_run(run_id, "promotable")
        writer.transition_run(run_id, "promoting")
        writer.record_promotion(run_id, candidate_sha="a" * 40, base_sha="b" * 40,
                                squash_sha="c" * 40, by="promote.py")
        writer.transition_run(run_id, "merged")
        writer.enqueue_outbox_event(run_id, {"schema": "workflow-fact/v1"})
        writer.transition_run(run_id, "projecting")
        writer.transition_run(run_id, "published", cost_usd=2.0)

    with ControlDB.open_read_only(db_path) as reader:
        run = reader.reconstruct_run(run_id)

    assert run.run.state is RunState.PUBLISHED
    assert run.run.spec_name == "control_db_publication"
    assert run.run.workflow_revision_id == "sha256:1d1c6a10ab5e"
    assert run.state_path == [
        "queued", "running", "verifying", "awaiting_approval", "verifying", "promotable",
        "promoting", "merged", "projecting", "published",
    ]
    # Both attempts survive, including the failed first one — the retry is visible.
    assert [(a.step_id, a.attempt_no, a.state.value, a.exit_code) for a in run.attempts] == [
        ("p1_control_db", 1, "failed", 1),
        ("p1_control_db", 2, "ok", 0),
    ]
    assert run.attempt_cost_usd == 2.0
    assert [g.candidate_sha for g in run.gate_results] == ["a" * 40]
    assert [a.operator for a in run.approvals] == ["controller"]
    assert [p.squash_sha for p in run.promotions] == ["c" * 40]
    assert len(run.outbox_events) == 1

    # The run never had a ledger — and needed none. That is the point.
    assert run.run.ledger_path == ""
    payload = run.to_dict()
    assert payload["run"]["state"] == "published"
    assert payload["state_path"][-1] == "published"
    assert len(payload["attempts"]) == 2
    # JSON-serialisable end to end, so the packet/ledger projections can render it directly.
    assert json.loads(json.dumps(payload))["gate_results"][0]["verdict"] == "pass"


def test_reconstructing_an_unknown_run_is_refused(db):
    with pytest.raises(UnknownRunError):
        db.reconstruct_run("run-nope")


# ── The single-writer contract ───────────────────────────────────────────────────────────────


def test_a_read_only_handle_refuses_every_write(db_path):
    """The orchestrator is the only writer; consumers get a handle that cannot forget that."""
    with ControlDB.open(db_path) as writer:
        run_id = make_run(writer)
        attempt = writer.start_attempt(run_id, step_id="p1")
        event = writer.enqueue_outbox_event(run_id, {"n": 1})

    with ControlDB.open_read_only(db_path) as reader:
        # Reads work.
        assert reader.get_run(run_id) is not None
        assert len(reader.attempts(run_id)) == 1
        # Writes do not — each one, not just the first.
        with pytest.raises(ReadOnlyControlDBError):
            reader.create_run(spec_name="x")
        with pytest.raises(ReadOnlyControlDBError):
            reader.transition_run(run_id, "running")
        with pytest.raises(ReadOnlyControlDBError):
            reader.start_attempt(run_id, step_id="p2")
        with pytest.raises(ReadOnlyControlDBError):
            reader.finish_attempt(attempt.attempt_id, AttemptState.OK)
        with pytest.raises(ReadOnlyControlDBError):
            reader.record_gate_result(run_id, step_id="p8", verdict="pass",
                                      candidate_sha="a" * 40)
        with pytest.raises(ReadOnlyControlDBError):
            reader.record_approval(run_id, candidate_sha="a" * 40, operator="op")
        with pytest.raises(ReadOnlyControlDBError):
            reader.record_promotion(run_id, candidate_sha="a" * 40)
        with pytest.raises(ReadOnlyControlDBError):
            reader.enqueue_outbox_event(run_id, {"n": 2})
        with pytest.raises(ReadOnlyControlDBError):
            reader.mark_outbox_delivered(event.event_id)
        with pytest.raises(ReadOnlyControlDBError):
            reader.record_watermark("registry", last_event_id="1-0")
        with pytest.raises(ReadOnlyControlDBError), reader.transaction():
            pass


def test_a_read_only_handle_never_creates_a_database(tmp_path):
    """'no runs' and 'the control state is missing' are different answers."""
    missing = tmp_path / "absent" / "control.db"
    with pytest.raises(ControlDBError, match="no control database"):
        ControlDB.open_read_only(missing)
    assert not missing.exists()


# ── Ledger → control-state mapping (the ledger as a projection) ──────────────────────────────


def test_ledger_success_maps_to_promotable_not_to_merged_or_published():
    """Passing phases authorise nothing on their own — that is the whole distinction."""
    assert run_state_from_ledger_state("succeeded") is RunState.PROMOTABLE
    assert run_state_from_ledger_state("awaiting_approval") is RunState.AWAITING_APPROVAL
    assert run_state_from_ledger_state("failed") is RunState.FAILED
    assert run_state_from_ledger_state("cancelled") is RunState.CANCELLED


def test_an_unknown_ledger_state_is_refused_not_guessed():
    with pytest.raises(UnknownStateError):
        run_state_from_ledger_state("completed")


def test_phase_status_maps_losslessly_onto_attempt_states():
    """The runner's own vocabulary, so back-filling attempts from ledgers invents nothing."""
    for status in ("ok", "failed", "awaiting", "skipped"):
        assert attempt_state_from_phase_status(status).value == status
    with pytest.raises(UnknownStateError):
        attempt_state_from_phase_status("probably-ok")


def test_summarize_states_reports_every_state_including_the_zeros(db):
    """A state that vanishes when empty makes 'none failed' look like 'not computed'."""
    run_id = make_run(db)
    advance(db, run_id, "running")
    counts = summarize_states(db.runs())
    assert set(counts) == set(MANDATED_RUN_STATES)
    assert counts["running"] == 1
    assert counts["failed"] == 0
