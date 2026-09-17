"""Tests for the session cache report (scripts/session_cache_report.py).

The report joins the plugin's delivery journal with the opencode session DB and computes the
token-weighted provider cache-miss rate (sum(miss)/sum(hit+miss)) grouped by cohort. These
tests pin: the formula, the completed-sample-only rule (a pending zero block is never a miss),
the cohort classification (journal join window, compaction summary + post-compaction recovery,
unavailability), the honest no-journal fallback, the normalization guard for providers that
report input inclusive of cache reads, and the exit codes.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "session_cache_report.py"
BASE = 1_700_000_000_000  # ms epoch


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("session_cache_report", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _iso(at_ms: int) -> str:
    return datetime.fromtimestamp(at_ms / 1000, tz=timezone.utc).isoformat()


def _make_db(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE session (id TEXT PRIMARY KEY, time_updated INTEGER)")
    con.execute(
        "CREATE TABLE message (id TEXT, session_id TEXT, time_created INTEGER, "
        "time_updated INTEGER, data TEXT)"
    )
    return con


def _message(
    con: sqlite3.Connection,
    *,
    mid: str,
    created: int,
    session: str = "ses_a",
    hit: int = 0,
    miss: int = 0,
    output: int = 0,
    reasoning: int = 0,
    total: int | None = None,
    mode: str | None = None,
    summary: bool | None = None,
) -> None:
    tokens: dict = {
        "input": miss,
        "output": output,
        "reasoning": reasoning,
        "cache": {"read": hit, "write": 0},
    }
    tokens["total"] = hit + miss + output + reasoning if total is None else total
    data: dict = {"role": "assistant", "tokens": tokens}
    if mode is not None:
        data["mode"] = mode
    if summary is not None:
        data["summary"] = summary
    con.execute(
        "INSERT INTO message (id, session_id, time_created, time_updated, data) VALUES (?,?,?,?,?)",
        (mid, session, created, created, json.dumps(data)),
    )


def _user(con: sqlite3.Connection, *, mid: str, created: int, session: str = "ses_a") -> None:
    """One user message row (the attach join's timeline anchor; no usage)."""
    con.execute(
        "INSERT INTO message (id, session_id, time_created, time_updated, data) VALUES (?,?,?,?,?)",
        (mid, session, created, created, json.dumps({"role": "user", "time": {"created": created}})),
    )


def _event(
    at_ms: int,
    *,
    session: str = "ses_a",
    kind: str = "refresh",
    surface: str = "messages.transform",
    message: str = "",
) -> dict:
    event = {
        "schema": "aio-context-event/v1",
        "at": _iso(at_ms),
        "session": session,
        "event": "attach" if surface == "chat.message" else "append",
        "kind": kind,
        "chars": 120,
        "surface": surface,
    }
    if message:
        event["message"] = message
    return event


def _write_events(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


def test_formula_and_cohorts_join_the_journal(tmp_path, mod):
    db = tmp_path / "opencode.db"
    con = _make_db(db)
    con.execute("INSERT INTO session (id, time_updated) VALUES ('ses_a', ?)", (BASE,))
    # The per-turn user-message ids anchor the identity join. NOTE the ordering the runtime
    # actually produces: `time.created` is stamped BEFORE the chat.message hook runs, so a
    # delivery event's `at` is GREATER than its user message's created (reviewer repair).
    _user(con, mid="u1", created=BASE - 1_000)  # turn 1: no attach (legacy shape)
    _message(con, mid="m1", created=BASE, hit=100, miss=900)  # first request of the turn
    _message(con, mid="m1b", created=BASE + 100, hit=10, miss=10)  # later tool-loop request
    _message(con, mid="m_pending", created=BASE + 500)  # zero-token block: not measured
    _user(con, mid="u2", created=BASE + 900)  # turn 2: an attach follows its creation
    _message(con, mid="m2", created=BASE + 1_000, hit=1_000, miss=0)  # first request
    _message(con, mid="m2b", created=BASE + 1_100, hit=20, miss=20)  # later request: reuse
    # A compaction summary and the post-compaction recovery request (its synthetic
    # continuation is a user message with no attach).
    _message(con, mid="m3", created=BASE + 2_000, hit=0, miss=5_000, mode="compaction", summary=True)
    _user(con, mid="u3", created=BASE + 2_900)
    _message(con, mid="m4", created=BASE + 3_000, hit=200, miss=300)
    # A request whose turn has no delivery event: honestly unclassified.
    _message(con, mid="m5", created=BASE + 4_000, hit=500, miss=500)
    # A continuation turn (no attach) whose fallback append carries the delivery.
    _user(con, mid="u4", created=BASE + 4_900)
    _message(con, mid="m6", created=BASE + 5_000, hit=50, miss=50)
    con.commit()
    con.close()

    events = tmp_path / "events.jsonl"
    _write_events(
        events,
        [
            # Turn u1 carries no attach: the fallback append (journaled with the user id)
            # classifies its FIRST request; the later request is unclassified (no delivery).
            _event(BASE + 50, kind="refresh", message="u1"),
            # Turn u2: a PERSISTED attach follows the user message — joined by IDENTITY, so
            # the first request is the continuation, and the later request is `reuse`.
            _event(BASE + 950, kind="continuation", surface="chat.message", message="u2"),
            # A compaction-hook event is NOT a per-request delivery: it must be ignored.
            _event(BASE + 2_050, kind="compaction", surface="session.compacting"),
            # Turn u4: the recovery fallback appends (journaled with the user id).
            _event(BASE + 5_050, kind="refresh", message="u4"),
        ],
    )

    report = mod.build_report(
        db, events, session_ids=["ses_a"], recent=0, everything=False, big_miss_tokens=5_000
    )
    cohorts = report["cohorts"]
    assert report["overall"]["requests"] == 8  # the pending block is skipped
    assert cohorts["refresh"]["requests"] == 2  # m1 (append) + m6 (append)
    assert cohorts["refresh"]["hit_tokens"] == 150
    assert cohorts["refresh"]["miss_tokens"] == 950
    assert cohorts["continuation"]["requests"] == 1  # m2 (the attach, first request of u2)
    assert cohorts["continuation"]["miss_rate"] == 0.0
    assert cohorts["reuse"]["requests"] == 1  # m2b — same-turn reuse, not a delivery
    assert cohorts["reuse"]["miss_rate"] == 0.5
    assert cohorts["compaction"]["requests"] == 2  # the summary + the recovery request
    assert cohorts["compaction"]["miss_tokens"] == 5_300
    assert cohorts["compaction"]["big_misses"] == 1  # the summary call (5,000 >= threshold)
    assert cohorts["unclassified"]["requests"] == 2  # m1b (no delivery) + m5 (no turn event)
    # The formula, token-weighted: sum(miss) / (sum(hit) + sum(miss)).
    assert report["overall"]["hit_tokens"] == 1_880
    assert report["overall"]["miss_tokens"] == 6_780
    assert report["overall"]["miss_rate"] == pytest.approx(6_780 / 8_660)
    assert report["sessions"][0]["session_id"] == "ses_a"
    assert report["formula"].startswith("sum(miss_tokens)")


def test_recovery_appends_classify_before_the_turn_attachment(mod):
    """Reviewer regression (2026-09-17, round 3): a turn whose attachment is an UNAVAILABLE
    notice recovers mid-turn — the recovery appends must classify their requests; the turn's
    attachment must not shadow them as ``reuse``.

    The combined sequence: unavailable attachment -> recovered-capsule append -> unchanged
    re-append, all within ONE user turn.
    """
    def assistant(mid: str, created: int, hit: int, miss: int) -> dict:
        return {
            "id": mid,
            "created": created,
            "data": {
                "role": "assistant",
                "tokens": {
                    "total": hit + miss,
                    "input": miss,
                    "output": 0,
                    "reasoning": 0,
                    "cache": {"read": hit, "write": 0},
                },
            },
        }

    messages = [
        {"id": "u1", "created": BASE - 1_000, "data": {"role": "user", "time": {"created": BASE - 1_000}}},
        assistant("m1", BASE, 10, 90),  # the unavailable attachment's first request
        assistant("m2", BASE + 1_000, 100, 900),  # the recovered-capsule append
        assistant("m3", BASE + 2_000, 200, 0),  # the unchanged re-append
    ]
    events = [
        {"at": BASE - 900, "kind": "unavailable", "surface": "chat.message", "message": "u1"},
        {"at": BASE + 1_050, "kind": "refresh", "surface": "messages.transform", "message": "u1"},
        {"at": BASE + 2_050, "kind": "continuation", "surface": "messages.transform", "message": "u1"},
    ]

    rows = mod._classify_session(messages, events)
    assert [row["cohort"] for row in rows] == ["continuation", "refresh", "continuation"]
    assert [row["detail"] for row in rows] == [
        "capsule unavailable",
        "new observation",
        "unchanged snapshot",
    ]


def test_without_a_journal_everything_is_unclassified_and_noted(tmp_path, mod):
    db = tmp_path / "opencode.db"
    con = _make_db(db)
    con.execute("INSERT INTO session (id, time_updated) VALUES ('ses_b', ?)", (BASE,))
    _message(con, mid="m1", created=BASE, hit=1, miss=99, session="ses_b")
    con.commit()
    con.close()

    report = mod.build_report(
        db, tmp_path / "missing.jsonl", session_ids=["ses_b"], recent=0, everything=False
    )
    assert report["cohorts"]["unclassified"]["requests"] == 1
    assert report["cohorts"]["refresh"]["requests"] == 0
    assert any("no delivery journal" in note for note in report["notes"])


def test_input_inclusive_of_cache_reads_is_normalized(mod):
    # Some providers report input INCLUDING cache reads; the hit must not be double-counted.
    hit, miss = mod._usage_of(
        {"tokens": {"total": 1_000, "input": 1_000, "output": 100, "reasoning": 0, "cache": {"read": 800}}}
    )
    assert (hit, miss) == (800, 100)
    # The deployment's shape (input + cache.read + output + reasoning == total) is untouched.
    assert mod._usage_of(
        {"tokens": {"total": 1_000, "input": 100, "output": 100, "reasoning": 0, "cache": {"read": 800}}}
    ) == (800, 100)
    # A pending zero block is not a measurement.
    assert mod._usage_of({"tokens": {"total": 0, "input": 0, "cache": {"read": 0}}}) is None


def test_main_exit_codes_and_json(tmp_path, mod, capsys):
    assert mod.main(["--db", str(tmp_path / "nope.db")]) == 2

    db = tmp_path / "opencode.db"
    con = _make_db(db)
    con.execute("INSERT INTO session (id, time_updated) VALUES ('ses_c', ?)", (BASE,))
    _message(con, mid="pending", created=BASE, session="ses_c")  # no completed sample
    con.commit()
    con.close()
    # An empty measurement renders honestly and exits 1 — never a fabricated rate.
    assert mod.main(["--db", str(db), "--session", "ses_c", "--no-journal"]) == 1
    output = capsys.readouterr().out
    assert "no measured requests" in output

    con = sqlite3.connect(db)
    _message(con, mid="m1", created=BASE + 1, hit=10, miss=90, session="ses_c")
    con.commit()
    con.close()
    assert mod.main(["--db", str(db), "--session", "ses_c", "--json", "--no-journal"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "session-cache-report/v1"
    assert payload["overall"]["miss_rate"] == pytest.approx(0.9)


def test_report_journal_appends_by_default(tmp_path, mod, monkeypatch, capsys):
    db = tmp_path / "opencode.db"
    con = _make_db(db)
    con.execute("INSERT INTO session (id, time_updated) VALUES ('ses_d', ?)", (BASE,))
    _message(con, mid="m1", created=BASE, hit=10, miss=90, session="ses_d")
    con.commit()
    con.close()

    journal = tmp_path / "reports.jsonl"
    monkeypatch.setenv("FINOPS_SESSION_CACHE_JOURNAL", str(journal))
    assert mod.main(["--db", str(db), "--session", "ses_d"]) == 0
    capsys.readouterr()
    lines = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 1
    assert lines[0]["schema"] == "session-cache-report/v1"
    assert lines[0]["overall"]["miss_tokens"] == 90

    # --no-journal leaves the journal alone.
    assert mod.main(["--db", str(db), "--session", "ses_d", "--no-journal"]) == 0
    capsys.readouterr()
    assert len(journal.read_text(encoding="utf-8").splitlines()) == 1
