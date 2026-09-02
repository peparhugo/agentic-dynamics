"""Control-packet tests — ``control-status/v1`` (``control_db_publication`` p4).

Driven in BOTH directions, per the repo's testing convention: for every rule the packet states,
one test proves it *holds* what it should and one proves it *refuses* what it should not. The
negative halves carry the weight here. A packet builder that emitted an empty
``safe_actions`` for every database would pass a naive "is the schema satisfied?" suite while
being useless; one that offered ``promote`` for every run would pass a naive "does it offer
actions?" suite while being actively dangerous — the master controller acts on this list.

The four claims the p4 mandate requires, each with its own section below:

1. **schema validity** — a rendered packet satisfies ``control-status/v1``, checked twice: by
   the module's dependency-free :func:`validate_packet` *and* by ``jsonschema`` against
   :data:`CONTROL_STATUS_SCHEMA`. Two independent encodings of one contract, so a packet that
   satisfies only the checker written by the same hand as the builder cannot pass;
2. **derived safe actions** — seeded database states produce exactly the right offers
   (awaiting → ``approve``, promotable → ``promote``, nothing actionable → empty), and the
   offers are always legal per the database's own transition graph;
3. **epoch advance** — ``control_epoch`` moves on a state transition, which is what lets a
   consumer detect "something happened" without diffing the whole packet;
4. **determinism** — the same database renders byte-identical JSON, so a master can diff turn N
   against turn N-1.

Storage is real throughout: every test opens an actual SQLite control database under
``tmp_path``. The thing under test is a *rendering of persisted state*, and a mocked database
would prove the mock's behaviour rather than the packet's. What IS injected is everything impure
— the repo head sha, the fleet heartbeats, and the clock — because those are exactly the inputs
the design deliberately lifted out of the builder to make it deterministic.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agentic_dynamics.control.control_db import (
    ALLOWED_TRANSITIONS,
    TERMINAL_RUN_STATES,
    ControlDB,
    GateVerdict,
    RunState,
)
from agentic_dynamics.control.control_status import (
    ACTIVE_RUN_STATES,
    CONTROL_STATUS_SCHEMA,
    DEFAULT_FAILED_LIMIT,
    DEGRADED_KEY,
    SCHEMA_ID,
    SafeAction,
    awaiting_approval_entries,
    build_packet,
    derive_safe_actions,
    format_packet,
    packet_json,
    read_repo_head_sha,
    run_ref,
    unhealthy_workers,
    validate_packet,
    worker_stale_after_seconds,
)

# NOT ``pytest.mark.fast``. The module-level fast mark this file shipped with (p4) violated the
# fast-path contract that ``tests/test_fast_path_gate.py`` enforces: the end-to-end cases below run
# the real ``scripts/control_status.py`` through ``subprocess``, which the fast smoke excludes by
# design (no real processes, no shared state). The whole module runs in the deterministic suite;
# only the sub-minute smoke skips it. Marking individual pure-unit cases fast would be a follow-up,
# not a silent re-mark of the module.

ROOT = Path(__file__).resolve().parent.parent


# ── Fixtures + seeding helpers ───────────────────────────────────────────────────────────────


@pytest.fixture()
def db(tmp_path: Path):
    """A real, empty control database under ``tmp_path``.

    Opened for WRITING because the tests are also the seeders. Production readers use
    ``ControlDB.open_read_only``; that the packet builder never needs write access is asserted
    separately in :func:`test_packet_builds_from_a_read_only_handle`.
    """
    with ControlDB.open(tmp_path / "control.db") as handle:
        yield handle


def seed_run(
    db: ControlDB,
    *,
    spec_name: str = "control_db_publication",
    candidate_sha: str = "a" * 40,
    state: RunState | None = None,
    run_id: str | None = None,
):
    """Create a run and walk it to ``state`` along the legal path.

    Walking the real transition graph rather than inserting a row in the target state directly is
    deliberate: it means every seeded fixture is a state the orchestrator could actually have
    produced, so a test can never assert correct behaviour for a state that cannot occur.
    """
    run = db.create_run(
        spec_name=spec_name,
        workflow_revision_id="pin-sha-0001",
        candidate_sha=candidate_sha,
        model="anthropic/claude-opus-5",
        run_id=run_id,
    )
    if state is None or state is RunState.QUEUED:
        return db.get_run(run.run_id)
    # The happy path to each interesting state, one legal hop at a time.
    path: dict[RunState, list[RunState]] = {
        RunState.RUNNING: [RunState.RUNNING],
        RunState.AWAITING_APPROVAL: [RunState.RUNNING, RunState.AWAITING_APPROVAL],
        RunState.VERIFYING: [RunState.RUNNING, RunState.VERIFYING],
        RunState.PROMOTABLE: [RunState.RUNNING, RunState.VERIFYING, RunState.PROMOTABLE],
        RunState.PROMOTING: [
            RunState.RUNNING,
            RunState.VERIFYING,
            RunState.PROMOTABLE,
            RunState.PROMOTING,
        ],
        RunState.MERGED: [
            RunState.RUNNING,
            RunState.VERIFYING,
            RunState.PROMOTABLE,
            RunState.PROMOTING,
            RunState.MERGED,
        ],
        RunState.PROJECTING: [
            RunState.RUNNING,
            RunState.VERIFYING,
            RunState.PROMOTABLE,
            RunState.PROMOTING,
            RunState.MERGED,
            RunState.PROJECTING,
        ],
        RunState.FAILED: [RunState.RUNNING, RunState.FAILED],
        RunState.CANCELLED: [RunState.RUNNING, RunState.CANCELLED],
    }
    for hop in path[state]:
        db.transition_run(run.run_id, hop, actor="test")
    return db.get_run(run.run_id)


def build(db: ControlDB, **kwargs):
    """``build_packet`` with the impure inputs pinned, so tests are deterministic by default."""
    kwargs.setdefault("repo_head_sha", "d" * 40)
    kwargs.setdefault("heartbeats", {})
    kwargs.setdefault("now", 1_000_000.0)
    return build_packet(db, **kwargs)


# ── 1. Schema validity ───────────────────────────────────────────────────────────────────────


def test_empty_database_renders_a_valid_packet(db) -> None:
    """A control plane with no runs still renders a complete, valid packet.

    The empty case is the one most likely to be wrong and the most consequential: it is what an
    actor sees on a quiet system, and every block must be *present and empty* rather than absent.
    A missing key would force consumers into defensive ``.get()`` calls, and a consumer that
    defaults a missing key is a consumer that silently invents state.
    """
    packet = build(db)
    assert validate_packet(packet) == []
    assert packet["schema"] == SCHEMA_ID
    for block in (
        "active_runs",
        "awaiting_approvals",
        "promotable_runs",
        "failed_runs",
        "unhealthy_workers",
        "safe_actions",
    ):
        assert packet[block] == [], f"{block} must be present and empty on a quiet system"


def test_populated_packet_is_valid_against_the_json_schema(db) -> None:
    """A packet covering every block validates against ``CONTROL_STATUS_SCHEMA`` via jsonschema.

    The independent check. :func:`validate_packet` and the schema object are two encodings of one
    contract written to be redundant; if they ever disagree, this test and the next one disagree
    with each other, which is exactly the alarm we want.
    """
    jsonschema = pytest.importorskip("jsonschema")

    seed_run(db, state=RunState.RUNNING)
    awaiting = seed_run(db, state=RunState.AWAITING_APPROVAL, candidate_sha="b" * 40)
    db.record_gate_result(
        awaiting.run_id,
        step_id="p4_control_packet",
        verdict=GateVerdict.PASS,
        candidate_sha=awaiting.candidate_sha,
        executor="pytest",
        gate_id="gate-checkpoint",
    )
    seed_run(db, state=RunState.PROMOTABLE, candidate_sha="c" * 40)
    seed_run(db, state=RunState.FAILED, candidate_sha="e" * 40)
    db.record_watermark("registry", last_event_id="1-0", source_head_event_id="1-0", lag_events=0)

    packet = build(
        db,
        heartbeats={"worker:story:w1": {"last_seen": "999000.0", "jobs": "3", "pid": "42"}},
    )

    jsonschema.validate(packet, CONTROL_STATUS_SCHEMA)
    assert validate_packet(packet) == []


@pytest.mark.parametrize(
    ("mutate", "expected_fragment"),
    [
        # Each case corrupts ONE rule of the contract. The point is not that the validator
        # rejects garbage — it is that it rejects the specific, plausible corruptions a buggy
        # builder would produce, each of which would otherwise reach an actor as a usable packet.
        (lambda p: p.update(schema="control-status/v2"), "schema is"),
        (lambda p: p.pop("safe_actions"), "missing required key: safe_actions"),
        (lambda p: p.update(control_epoch=-1), "control_epoch"),
        (lambda p: p.update(control_epoch=True), "control_epoch"),
        (lambda p: p.update(unexpected="x"), "unknown key: unexpected"),
        (
            lambda p: p["safe_actions"].append({"action": "delete", "run_id": "r", "gate_id": ""}),
            "not in the vocabulary",
        ),
        (lambda p: p["projection_lag"].pop("registry"), "missing registry"),
        (lambda p: p["projection_lag"].update(registry="0"), "must be an integer or null"),
        (lambda p: p["active_runs"].append({"run_id": "r"}), "is missing spec_name"),
        (lambda p: p.update(projection_lag=[]), "projection_lag must be an object"),
    ],
)
def test_validator_refuses_a_malformed_packet(db, mutate, expected_fragment) -> None:
    """The negative direction: each single-rule corruption is caught, and named."""
    packet = build(db)
    mutate(packet)
    errors = validate_packet(packet)
    assert any(expected_fragment in e for e in errors), (
        f"expected an error containing {expected_fragment!r}, got {errors}"
    )


def test_validator_refuses_a_non_object() -> None:
    """A list, a string, or ``None`` is not a packet — refused without raising."""
    for candidate in ([], "packet", None, 7):
        assert validate_packet(candidate), f"{candidate!r} must not validate"


# ── 2. Derived safe actions ──────────────────────────────────────────────────────────────────


def test_awaiting_run_yields_an_approve_action_bound_to_its_gate(db) -> None:
    """awaiting_approval + an unapproved gate → ``approve``, naming gate AND candidate sha.

    The identifiers are the deliverable. The doctrine tells the master to act only on ids the
    packet returns, so an ``approve`` that did not name the gate and the tree would be an
    instruction to guess.
    """
    run = seed_run(db, state=RunState.AWAITING_APPROVAL)
    db.record_gate_result(
        run.run_id,
        step_id="p4_control_packet",
        verdict=GateVerdict.PASS,
        candidate_sha=run.candidate_sha,
        executor="pytest",
        gate_id="gate-checkpoint",
    )

    packet = build(db)

    assert packet["awaiting_approvals"] == [
        {
            "run_id": run.run_id,
            "gate_id": "gate-checkpoint",
            "candidate_sha": run.candidate_sha,
            "spec_name": run.spec_name,
        }
    ]
    approve = [a for a in packet["safe_actions"] if a["action"] == SafeAction.APPROVE.value]
    assert approve == [
        {
            "action": "approve",
            "run_id": run.run_id,
            "gate_id": "gate-checkpoint",
            "candidate_sha": run.candidate_sha,
        }
    ]


def test_awaiting_run_without_a_gate_row_still_yields_an_approve(db) -> None:
    """A run stopped for approval with no gate row is still surfaced — with an empty ``gate_id``.

    Dropping it would hide a stopped run from the one surface whose job is to show stopped runs.
    ``ControlDB.record_approval`` accepts an empty ``gate_id``, so the offer is actionable.
    """
    run = seed_run(db, state=RunState.AWAITING_APPROVAL)
    packet = build(db)
    assert packet["awaiting_approvals"] == [
        {
            "run_id": run.run_id,
            "gate_id": "",
            "candidate_sha": run.candidate_sha,
            "spec_name": run.spec_name,
        }
    ]
    assert [a["action"] for a in packet["safe_actions"] if a["action"] == "approve"] == ["approve"]


def test_an_already_approved_gate_is_not_offered_again(db) -> None:
    """The negative direction: an approved gate stops appearing.

    What is outstanding once an operator has signed is the orchestrator's *transition*, not a
    second human judgement. Re-offering it is how duplicate approvals get manufactured — and a
    duplicate approval is indistinguishable, after the fact, from an approval of a different tree.
    """
    run = seed_run(db, state=RunState.AWAITING_APPROVAL)
    db.record_gate_result(
        run.run_id,
        step_id="p4_control_packet",
        verdict=GateVerdict.PASS,
        candidate_sha=run.candidate_sha,
        executor="pytest",
        gate_id="gate-checkpoint",
    )
    db.record_approval(
        run.run_id,
        gate_id="gate-checkpoint",
        candidate_sha=run.candidate_sha,
        operator="operator@example",
    )

    packet = build(db)
    assert packet["awaiting_approvals"] == []
    assert [a for a in packet["safe_actions"] if a["action"] == "approve"] == []


def test_an_approval_for_a_different_sha_does_not_satisfy_the_gate(db) -> None:
    """A stale approval must never clear a checkpoint on a rewritten tree.

    This is ``gate_results.candidate_sha``'s whole reason for existing, carried into the packet:
    the approval below names the same gate but a *different* sha, so the decision is still owed.
    """
    run = seed_run(db, state=RunState.AWAITING_APPROVAL, candidate_sha="a" * 40)
    db.record_gate_result(
        run.run_id,
        step_id="p4_control_packet",
        verdict=GateVerdict.PASS,
        candidate_sha=run.candidate_sha,
        executor="pytest",
        gate_id="gate-checkpoint",
    )
    db.record_approval(
        run.run_id,
        gate_id="gate-checkpoint",
        candidate_sha="f" * 40,  # an earlier tree
        operator="operator@example",
    )

    packet = build(db)
    assert [e["gate_id"] for e in packet["awaiting_approvals"]] == ["gate-checkpoint"]


def test_promotable_run_yields_a_promote_action(db) -> None:
    """promotable → ``promote``, and the run also appears in ``promotable_runs``."""
    run = seed_run(db, state=RunState.PROMOTABLE)
    packet = build(db)

    assert [r["run_id"] for r in packet["promotable_runs"]] == [run.run_id]
    assert {
        "action": "promote",
        "run_id": run.run_id,
        "gate_id": "",
        "candidate_sha": run.candidate_sha,
    } in packet["safe_actions"]


def test_no_actionable_runs_yields_no_actions(db) -> None:
    """The negative direction: terminal-only state offers nothing.

    A ``failed`` run cannot be approved, promoted, or cancelled — every edge out of a terminal
    state was removed by the database's own graph, and the packet must not invent one.
    """
    seed_run(db, state=RunState.FAILED)
    seed_run(db, state=RunState.CANCELLED, candidate_sha="b" * 40)

    packet = build(db)
    assert packet["safe_actions"] == []
    assert packet["active_runs"] == []
    assert len(packet["failed_runs"]) == 1


def test_merged_run_is_active_but_not_cancellable(db) -> None:
    """A merged run stays visible as active, yet is never offered for cancellation.

    Cancelling work that is already on main is a lie: the commits exist. The database encodes
    that (``CANCELLED`` is unreachable from ``MERGED``); this asserts the packet reads the same
    graph rather than restating the rule and drifting from it.
    """
    run = seed_run(db, state=RunState.MERGED)
    packet = build(db)

    assert [r["run_id"] for r in packet["active_runs"]] == [run.run_id]
    assert [a for a in packet["safe_actions"] if a["action"] == "cancel"] == []


def test_running_run_is_cancellable(db) -> None:
    """The positive half of the pair above: pre-merge work IS cancellable."""
    run = seed_run(db, state=RunState.RUNNING)
    packet = build(db)
    assert {
        "action": "cancel",
        "run_id": run.run_id,
        "gate_id": "",
        "candidate_sha": run.candidate_sha,
    } in packet["safe_actions"]


def test_every_offered_action_is_legal_in_the_databases_own_transition_graph(db) -> None:
    """The structural invariant: the packet can never offer what the database would refuse.

    Seeds one run in every non-terminal state, then checks each offered action against
    ``ALLOWED_TRANSITIONS`` — the same graph ``ControlDB.transition_run`` enforces. If a future
    edit to the lifecycle removes an edge, this fails immediately instead of at the moment an
    actor tries to use the offer.
    """
    states = {}
    for i, state in enumerate(sorted(ACTIVE_RUN_STATES, key=lambda s: s.value)):
        run = seed_run(db, state=state, candidate_sha=f"{i:040d}")
        states[run.run_id] = state

    packet = build(db)
    assert packet["safe_actions"], "a database full of live runs must offer something"

    # An action's target state, i.e. what performing it would transition the run into.
    target = {
        SafeAction.CANCEL.value: RunState.CANCELLED,
        SafeAction.PROMOTE.value: RunState.PROMOTING,
    }
    for action in packet["safe_actions"]:
        state = states[action["run_id"]]
        if action["action"] == SafeAction.APPROVE.value:
            # Approving is a recorded decision, not a transition; its precondition is the state.
            assert state is RunState.AWAITING_APPROVAL
            continue
        assert target[action["action"]] in ALLOWED_TRANSITIONS[state], (
            f"{action['action']} offered for a run in {state.value}, "
            f"which the database would refuse"
        )


def test_safe_actions_are_ordered_approve_then_promote_then_cancel(db) -> None:
    """Advancing decisions before the destructive one, with a total order under it.

    The ordering is both a weak prior (do the approvals first) and the determinism guarantee:
    ties break on ``run_id`` then ``gate_id``, so the list is a function of the database alone.
    """
    seed_run(db, state=RunState.AWAITING_APPROVAL, candidate_sha="a" * 40, run_id="run-zzz")
    seed_run(db, state=RunState.PROMOTABLE, candidate_sha="b" * 40, run_id="run-mmm")
    seed_run(db, state=RunState.RUNNING, candidate_sha="c" * 40, run_id="run-aaa")

    safe_actions = build(db)["safe_actions"]
    # All three runs are pre-merge, so all three are ALSO cancellable — the advancing offers
    # come first, then every cancel. (A promotable run being cancellable is the graph's rule,
    # not an accident: the work has not reached main yet.)
    assert [a["action"] for a in safe_actions] == [
        "approve",
        "promote",
        "cancel",
        "cancel",
        "cancel",
    ]
    # Within the cancel group, the tiebreak is run_id — a total order, hence deterministic.
    cancels = [a["run_id"] for a in safe_actions if a["action"] == "cancel"]
    assert cancels == ["run-aaa", "run-mmm", "run-zzz"]


def test_derive_safe_actions_is_a_pure_function() -> None:
    """``derive_safe_actions`` needs no database — it is a function of state, and testable alone.

    Called here with hand-built inputs (no db at all) to pin that the derivation reads only its
    arguments. If it ever grew a hidden read — of Redis, of a file, of the clock — this fails.
    """
    assert derive_safe_actions(awaiting=[], runs_by_state={}) == []
    only_approve = derive_safe_actions(
        awaiting=[{"run_id": "r1", "gate_id": "g1", "candidate_sha": "s1"}],
        runs_by_state={},
    )
    assert only_approve == [
        {"action": "approve", "run_id": "r1", "gate_id": "g1", "candidate_sha": "s1"}
    ]


def test_approve_actions_correspond_one_to_one_with_awaiting_approvals(db) -> None:
    """The stated invariant, asserted: every approve names a listed decision, and vice versa."""
    for i in range(3):
        run = seed_run(db, state=RunState.AWAITING_APPROVAL, candidate_sha=f"{i:040d}")
        db.record_gate_result(
            run.run_id,
            step_id="p4",
            verdict=GateVerdict.PASS,
            candidate_sha=run.candidate_sha,
            executor="pytest",
            gate_id=f"gate-{i}",
        )

    packet = build(db)
    approvals = {(e["run_id"], e["gate_id"]) for e in packet["awaiting_approvals"]}
    approves = {
        (a["run_id"], a["gate_id"])
        for a in packet["safe_actions"]
        if a["action"] == SafeAction.APPROVE.value
    }
    assert approvals == approves
    assert len(approvals) == 3


# ── 3. Epoch advance ─────────────────────────────────────────────────────────────────────────


def test_control_epoch_advances_on_a_transition(db) -> None:
    """The epoch moves when state moves — the cheap "did anything happen?" signal.

    A master that reloads the packet every turn can compare one integer instead of diffing the
    whole document. That only works if the counter is monotonic and actually bumped, which is a
    claim about the *database*; the packet's job is to carry it faithfully.
    """
    run = seed_run(db, state=RunState.RUNNING)
    before = build(db)["control_epoch"]

    db.transition_run(run.run_id, RunState.VERIFYING, actor="test")
    after = build(db)["control_epoch"]

    assert after > before


def test_control_epoch_does_not_move_without_a_transition(db) -> None:
    """The negative direction: reading the packet is not itself an event.

    If merely observing bumped the epoch, the signal would be pure noise — every poll would look
    like a change, and a master would re-plan on every turn for no reason.
    """
    seed_run(db, state=RunState.RUNNING)
    assert build(db)["control_epoch"] == build(db)["control_epoch"]


def test_control_epoch_is_monotonic_across_many_transitions(db) -> None:
    """Strictly increasing across a full lifecycle walk — never reset, never reused."""
    run = seed_run(db)
    epochs = [build(db)["control_epoch"]]
    for state in (RunState.RUNNING, RunState.VERIFYING, RunState.PROMOTABLE):
        db.transition_run(run.run_id, state, actor="test")
        epochs.append(build(db)["control_epoch"])
    assert epochs == sorted(set(epochs)), f"epoch must strictly increase, got {epochs}"


# ── 4. Determinism ───────────────────────────────────────────────────────────────────────────


def test_packet_is_byte_identical_for_a_fixed_database(db) -> None:
    """Same database + same injected inputs → same JSON, byte for byte.

    This is what makes the packet diffable. "Nothing changed" must be observable as an equal
    string, not as a structure a consumer has to walk and compare field by field.
    """
    for i in range(3):
        seed_run(db, state=RunState.RUNNING, candidate_sha=f"{i:040d}")
    seed_run(db, state=RunState.AWAITING_APPROVAL, candidate_sha="b" * 40)
    seed_run(db, state=RunState.PROMOTABLE, candidate_sha="c" * 40)

    first = packet_json(build(db))
    second = packet_json(build(db))
    assert first == second


def test_packet_ordering_is_independent_of_insertion_order(tmp_path: Path) -> None:
    """Two databases seeded in different orders render the same run set in the same order.

    Determinism that depended on rowid order would be an accident that survives until the first
    resumed run. The ordering contract is ``started_at DESC, run_id DESC`` — a *total* order —
    so it is a property of the data, not of the write sequence.
    """

    def render(order: list[str]) -> list[str]:
        with ControlDB.open(tmp_path / f"{'-'.join(order)}.db") as handle:
            for run_id in order:
                handle.create_run(
                    spec_name="s",
                    workflow_revision_id="pin",
                    candidate_sha=run_id * 8,
                    model="m",
                    run_id=run_id,
                    started_at="2026-09-02T00:00:00+00:00",  # identical: forces the id tiebreak
                )
                handle.transition_run(run_id, RunState.RUNNING, actor="test")
            return [r["run_id"] for r in build(handle)["active_runs"]]

    assert render(["aaa", "bbb", "ccc"]) == render(["ccc", "aaa", "bbb"])


def test_packet_json_key_order_is_fixed(db) -> None:
    """The documented top-level key order is the emitted order (identity → state → actions)."""
    packet = build(db)
    assert list(packet) == [
        "schema",
        "repo_head_sha",
        "control_epoch",
        "active_runs",
        "awaiting_approvals",
        "promotable_runs",
        "failed_runs",
        "unhealthy_workers",
        "projection_lag",
        "safe_actions",
        DEGRADED_KEY,
    ]
    # The serialised form preserves it (json.dumps must not be sorting keys behind our back).
    assert list(json.loads(packet_json(packet))) == list(packet)


# ── Projection lag: p3's block, and its null-not-zero rule ───────────────────────────────────


def test_projection_lag_carries_every_projection_and_nulls_the_unknown(db) -> None:
    """Every known projection has a key; one that never reported is ``null``, never ``0``.

    A fabricated ``0`` reads as "fully caught up" — the answer a publication gate would happily
    act on. The unknown ones are additionally named in ``degraded``, so the condition is visible
    without inspecting each value.
    """
    db.record_watermark("registry", last_event_id="5-0", source_head_event_id="5-0", lag_events=0)
    db.record_watermark("chroma", last_event_id="2-0", source_head_event_id="5-0", lag_events=3)

    packet = build(db)
    lag = packet["projection_lag"]

    assert lag["registry"] == 0
    assert lag["chroma"] == 3
    assert lag["neo4j"] is None, "a projection that never reported must be null, not 0"
    assert lag["ledger"] is None
    assert any(n["surface"] == "projection_lag" for n in packet[DEGRADED_KEY])


def test_a_fully_reported_projection_set_produces_no_lag_degradation(db) -> None:
    """The negative half: when every projection has reported, nothing is flagged."""
    for projection in ("registry", "chroma", "neo4j", "ledger"):
        db.record_watermark(
            projection, last_event_id="5-0", source_head_event_id="5-0", lag_events=0
        )
    packet = build(db)
    assert [n for n in packet[DEGRADED_KEY] if n["surface"] == "projection_lag"] == []


def test_a_stale_projections_recorded_zero_lag_is_not_carried_as_zero(db) -> None:
    """A STALE projector's recorded lag is not believable — the packet must not render it as 0.

    p3's rule ("a zero recorded four hours ago describes four-hour-old reality") is carried
    through to the ONE packet: a watermark whose ``last_success_at`` has aged past the staleness
    window renders its lag as ``null`` and names the projection in ``degraded``. Rendering the
    recorded ``0`` would let a dead projector read as "caught up" — exactly the false-current
    answer the packet exists to prevent. (A live ``LAGGING`` projection keeps its number: being
    behind *now* is the signal, not the failure.)
    """
    from datetime import datetime, timedelta, timezone

    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    db.record_watermark(
        "registry", last_event_id="5-0", source_head_event_id="5-0", lag_events=0,
        last_success_at=old,
    )
    db.record_watermark(
        "chroma", last_event_id="2-0", source_head_event_id="5-0", lag_events=3,
        last_success_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    packet = build(db)
    assert packet["projection_lag"]["registry"] is None, \
        "a stale recorded 0 must not render as caught-up"
    assert packet["projection_lag"]["chroma"] == 3, "a live lagging projection keeps its number"
    assert any(
        n["surface"] == "projection_lag" and "registry" in n["reason"]
        for n in packet[DEGRADED_KEY]
    )


# ── Worker health ────────────────────────────────────────────────────────────────────────────


def test_stale_worker_is_reported_and_a_live_one_is_not() -> None:
    """Both directions in one: a beating worker is silent, a stopped one is named."""
    now = 1_000_000.0
    result = unhealthy_workers(
        {
            "worker:story:alive": {"last_seen": str(now - 5), "jobs": "2", "pid": "10"},
            "worker:story:dead": {"last_seen": str(now - 600), "jobs": "9", "pid": "11"},
        },
        now=now,
        stale_after_s=45.0,
    )
    assert [w["worker"] for w in result] == ["worker:story:dead"]
    assert result[0]["reason"] == "stale"
    assert result[0]["age_seconds"] == 600.0
    assert result[0]["worker_type"] == "story"
    assert result[0]["worker_id"] == "dead"


def test_worker_without_a_usable_timestamp_has_null_age_not_a_number() -> None:
    """An unparseable heartbeat is ``no_heartbeat`` with ``age_seconds: null``.

    Not a huge number, and not zero. We do not know how long it has been silent, and inventing a
    duration would be inventing evidence about a dead process.
    """
    result = unhealthy_workers({"worker:kb:x": {"jobs": "0"}}, now=1_000_000.0)
    assert result[0]["reason"] == "no_heartbeat"
    assert result[0]["age_seconds"] is None
    assert result[0]["last_seen"] is None


def test_worker_fields_decode_from_bytes() -> None:
    """Redis clients configured without ``decode_responses`` must not break the surface."""
    now = 1_000_000.0
    result = unhealthy_workers(
        {b"worker:review:r1": {b"last_seen": b"999000.0", b"jobs": b"1", b"pid": b"7"}},
        now=now,
        stale_after_s=45.0,
    )
    assert result[0]["worker"] == "worker:review:r1"
    assert result[0]["jobs"] == 1


def test_unobserved_workers_are_degraded_not_silently_empty(db) -> None:
    """``heartbeats=None`` renders an empty list PLUS a note — never bare good news.

    The distinction the whole surface rests on: ``unhealthy_workers: []`` must mean "we looked
    and everyone is alive", so "we could not look" has to say so somewhere.
    """
    packet = build_packet(db, repo_head_sha="d" * 40, heartbeats=None)
    assert packet["unhealthy_workers"] == []
    assert any(n["surface"] == "unhealthy_workers" for n in packet[DEGRADED_KEY])


def test_observed_and_healthy_workers_produce_no_note(db) -> None:
    """The negative half: an observed, healthy fleet is quiet in ``degraded``."""
    packet = build(
        db, heartbeats={"worker:story:w": {"last_seen": "999999.0"}}, now=1_000_000.0
    )
    assert packet["unhealthy_workers"] == []
    assert [n for n in packet[DEGRADED_KEY] if n["surface"] == "unhealthy_workers"] == []


def test_worker_stale_threshold_honours_the_environment_override(monkeypatch) -> None:
    """The override applies; a malformed or non-positive one falls back rather than raising."""
    monkeypatch.setenv("FINOPS_WORKER_STALE_S", "5")
    assert worker_stale_after_seconds() == 5.0
    monkeypatch.setenv("FINOPS_WORKER_STALE_S", "not-a-number")
    assert worker_stale_after_seconds() == 45.0
    monkeypatch.setenv("FINOPS_WORKER_STALE_S", "-1")
    assert worker_stale_after_seconds() == 45.0


# ── Failed-run truncation ────────────────────────────────────────────────────────────────────


def test_failed_runs_are_capped_and_the_truncation_is_reported(db) -> None:
    """Over the limit, the block is cut — and the cut is announced, never silent.

    A surface that quietly truncates reads as complete, which is how "we only had three failures"
    becomes a belief. The note is the difference between a summary and a lie.
    """
    for i in range(5):
        seed_run(db, state=RunState.FAILED, candidate_sha=f"{i:040d}")

    packet = build(db, failed_limit=2)
    assert len(packet["failed_runs"]) == 2
    assert any(
        n["surface"] == "failed_runs" and "truncated" in n["reason"] for n in packet[DEGRADED_KEY]
    )


def test_failed_runs_under_the_limit_are_not_reported_as_truncated(db) -> None:
    """The negative half: exactly at the limit is complete, and says nothing."""
    for i in range(2):
        seed_run(db, state=RunState.FAILED, candidate_sha=f"{i:040d}")
    packet = build(db, failed_limit=2)
    assert len(packet["failed_runs"]) == 2
    assert [n for n in packet[DEGRADED_KEY] if n["surface"] == "failed_runs"] == []


def test_default_failed_limit_is_applied(db) -> None:
    """The documented default is the effective default (not silently unbounded)."""
    assert build(db)["failed_runs"] == []
    assert DEFAULT_FAILED_LIMIT > 0


# ── Read-only + shape guarantees ─────────────────────────────────────────────────────────────


def test_packet_builds_from_a_read_only_handle(tmp_path: Path) -> None:
    """The builder never needs write access — the single-writer contract holds for consumers.

    Structural, not polite: the read-only handle opens SQLite with ``mode=ro``, so a builder that
    tried to write would fail here rather than corrupting the orchestrator's state.
    """
    path = tmp_path / "control.db"
    with ControlDB.open(path) as writer:
        seed_run(writer, state=RunState.PROMOTABLE)

    with ControlDB.open_read_only(path) as reader:
        packet = build(reader)
    assert validate_packet(packet) == []
    assert len(packet["promotable_runs"]) == 1


def test_active_run_states_is_exactly_the_non_terminal_vocabulary() -> None:
    """The active set is derived, not hand-listed — a new state cannot silently vanish."""
    assert frozenset(RunState) - TERMINAL_RUN_STATES == ACTIVE_RUN_STATES
    assert not ACTIVE_RUN_STATES & TERMINAL_RUN_STATES
    assert len(ACTIVE_RUN_STATES) == 8  # twelve states, four terminal


def test_run_ref_carries_the_identifiers_an_actor_needs(db) -> None:
    """A run reference names the run, the tree, and the mandate it is executing."""
    run = seed_run(db, state=RunState.RUNNING)
    ref = run_ref(run)
    assert ref["run_id"] == run.run_id
    assert ref["candidate_sha"] == run.candidate_sha
    assert ref["workflow_revision_id"] == "pin-sha-0001"
    assert ref["state"] == "running"


def test_awaiting_entries_ignore_runs_in_other_states(db) -> None:
    """Only ``awaiting_approval`` produces entries — a verifying run owes nobody a decision."""
    seed_run(db, state=RunState.VERIFYING)
    seed_run(db, state=RunState.PROMOTABLE, candidate_sha="b" * 40)
    assert awaiting_approval_entries(db, db.runs()) == []


def test_format_packet_renders_without_raising(db) -> None:
    """The human rendering survives both a populated and an empty packet.

    It is the glance, not the record — but a formatter that raises on the empty case would take
    the operator's view away exactly when the system is quiet and they are checking why.
    """
    assert "control-status/v1" in format_packet(build(db))
    seed_run(db, state=RunState.AWAITING_APPROVAL)
    rendered = format_packet(build(db))
    assert "approve" in rendered


# ── The CLI seam ─────────────────────────────────────────────────────────────────────────────


def test_cli_emits_a_valid_packet(tmp_path: Path) -> None:
    """``scripts/control_status.py --json`` prints a packet that validates.

    End-to-end through the real subprocess, because the script's job is precisely the wiring the
    unit tests inject around: opening the database read-only, collecting the impure inputs, and
    printing parseable JSON on stdout with diagnostics on stderr.
    """
    path = tmp_path / "control.db"
    with ControlDB.open(path) as writer:
        seed_run(writer, state=RunState.PROMOTABLE)

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "control_status.py"), "--json",
         "--db", str(path), "--no-workers"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    packet = json.loads(proc.stdout)
    assert validate_packet(packet) == []
    assert len(packet["promotable_runs"]) == 1


def test_cli_is_deterministic_across_invocations(tmp_path: Path) -> None:
    """Two runs of the command over an unchanged database print identical JSON.

    The end-to-end form of the determinism claim: the master diffs command output, not an
    in-process object, so the guarantee has to survive the CLI's own collectors. ``--no-workers``
    pins the one input that genuinely changes with wall-clock time.
    """
    path = tmp_path / "control.db"
    with ControlDB.open(path) as writer:
        seed_run(writer, state=RunState.AWAITING_APPROVAL)

    cmd = [sys.executable, str(ROOT / "scripts" / "control_status.py"), "--json",
           "--db", str(path), "--no-workers", "--compact"]
    first = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), timeout=120)
    second = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), timeout=120)
    assert first.returncode == 0 and second.returncode == 0
    assert first.stdout == second.stdout
    assert "\n" not in first.stdout.strip(), "--compact must emit a single line"


def test_cli_distinguishes_a_missing_control_db_from_an_empty_one(tmp_path: Path) -> None:
    """No database → exit 3 and an ``error`` envelope, NOT an empty packet.

    The most important negative test in the file. "The orchestrator has never run" and "there is
    nothing to do" are opposite situations, and a reader that conflated them would confidently
    report an idle, healthy control plane that does not exist.
    """
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "control_status.py"), "--json",
         "--db", str(tmp_path / "absent.db"), "--no-workers"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=120,
    )
    assert proc.returncode == 3
    envelope = json.loads(proc.stdout)
    assert envelope["error"] == "control_db_unavailable"
    assert "active_runs" not in envelope, "an error envelope must not masquerade as a packet"
    assert not (tmp_path / "absent.db").exists(), "a reader must never create the database"


def test_cli_human_output_is_not_json(tmp_path: Path) -> None:
    """Without ``--json`` the command prints the operator glance, not a machine payload."""
    path = tmp_path / "control.db"
    with ControlDB.open(path) as writer:
        seed_run(writer, state=RunState.RUNNING)

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "control_status.py"),
         "--db", str(path), "--no-workers"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=120,
    )
    assert proc.returncode == 0
    assert proc.stdout.startswith("control-status/v1")
    with pytest.raises(json.JSONDecodeError):
        json.loads(proc.stdout)


def test_repo_head_sha_reports_failure_instead_of_fabricating(tmp_path: Path) -> None:
    """A non-git directory yields ``("", reason)`` — never a made-up sha, never an exception.

    The packet must still render when git is unavailable: taking away the operator's view of the
    control plane at the moment the machine is broken is the opposite of what this surface is for.
    """
    sha, error = read_repo_head_sha(tmp_path)
    assert sha == ""
    assert error


def test_repo_head_sha_reads_the_real_checkout() -> None:
    """The positive half: inside the repo, a 40-character sha with no error."""
    sha, error = read_repo_head_sha(ROOT)
    assert error == ""
    assert len(sha) == 40
