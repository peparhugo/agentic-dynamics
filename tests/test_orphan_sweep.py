"""Server-level orphan sweep tests (cap_runner_hardening2 §Gap 1).

Both directions of the design's acceptance criteria, the ledger/flag-only contract, the
zombie reaping seam, and the terra-orphan REPLAY as the regression proof. The replay runs
against a frozen reconstruction of the real opencode session store
(``tests/fixtures/terra_orphan_snapshot.json`` — the parent f3 session, its ``task`` part
delegating to the deepseek pipeline-ops subagent, and the subagent's transcript timestamps),
so the proof is hermetic and deterministic (no live 50 GB DB dependency).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from agentic_dynamics.control.orphan_sweep import (
    CRASH_GRACE_S,
    ORPHAN_EVENTS_KEY,
    PartRecord,
    SessionRecord,
    SQLiteSessionStore,
    detect_orphans,
    load_recorded_orphan_ids,
    orphan_id,
    reap_orphaned_subagents,
    record_orphan,
    sweep_once,
)
from agentic_dynamics.knowledge import knowledge_stream as ks

FIXTURE = Path(__file__).parent / "fixtures" / "terra_orphan_snapshot.json"

# ── synthetic fixture builders ───────────────────────────────────────────────


def make_session(sid, *, parent=None, title="subagent", model="deepseek/deepseek-v4-flash",
                 created=100_000_000, updated=100_000_000):
    return SessionRecord(
        id=sid, parent_id=parent, title=title, model=model,
        time_created=created, time_updated=updated,
    )


def make_part(pid, sid, t, kind="text", data=None):
    return PartRecord(
        id=pid, session_id=sid, time_created=t, type=kind,
        data=data if data is not None else {"type": kind},
    )


def task_part(pid, sid, t, target_sub):
    return PartRecord(
        id=pid, session_id=sid, time_created=t, type="tool",
        data={"type": "tool", "tool": "task", "state": {
            "status": "running", "metadata": {"sessionId": target_sub},
        }},
    )


def completed_subagent_scenario(*, now=100_400_000, crash_grace_s=CRASH_GRACE_S):
    """Parent silent after spawn; subagent completed at spawn+60s. Detected as orphan."""
    parent = make_session("ses_parent", parent=None, title="Implement (fork)", created=100_000_000)
    sub = make_session(
        "ses_sub", parent="ses_parent", title="Harden (@pipeline-ops subagent)",
        created=100_001_000,
    )
    parts = [
        task_part("prt_task", "ses_parent", 100_000_000, "ses_sub"),
        make_part("prt_ss", "ses_sub", 100_001_000, "step-start"),
        make_part("prt_sf", "ses_sub", 100_060_000, "step-finish"),
        make_part("prt_text", "ses_sub", 100_060_000, "text"),
    ]
    return [parent, sub], parts, now, crash_grace_s


# ── detection: both directions ───────────────────────────────────────────────


def test_synthetic_orphan_parent_silent_subagent_completed_is_detected():
    sessions, parts, now, _ = completed_subagent_scenario()
    orphans = detect_orphans(sessions, parts, now_ms=now)

    assert len(orphans) == 1
    orphan = orphans[0]
    assert orphan.parent_session_id == "ses_parent"
    assert orphan.subagent_session_id == "ses_sub"
    assert orphan.terminated_reason == "completed"
    assert orphan.result_available is True
    assert orphan.spawn_ms == 100_000_000
    # idle counts from the subagent's termination: (100_400_000 - 100_060_000)/60000 = 5.67
    assert orphan.idle_minutes == pytest.approx((100_400_000 - 100_060_000) / 60000.0, abs=0.01)
    assert orphan.detected_at.endswith("Z")
    assert orphan.flagged is True
    assert orphan.orphan_id == orphan_id("ses_parent", "ses_sub")


def test_live_parent_still_stepping_with_running_subagent_is_never_flagged():
    # Parent writes steps AFTER spawn; subagent is mid-work (step-start, no step-finish,
    # recently active). Both arms of the rule must fail → no orphan.
    parent = make_session("ses_parent", created=100_000_000)
    sub = make_session(
        "ses_sub", parent="ses_parent", created=100_001_000, updated=100_200_000,
    )
    parts = [
        task_part("prt_task", "ses_parent", 100_000_000, "ses_sub"),
        make_part("prt_parent_step", "ses_parent", 100_050_000, "step-start"),
        make_part("prt_parent_tool", "ses_parent", 100_100_000, "tool"),
        make_part("prt_ss", "ses_sub", 100_001_000, "step-start"),
        make_part("prt_reason", "ses_sub", 100_180_000, "reasoning"),
    ]
    orphans = detect_orphans([parent, sub], parts, now_ms=100_400_000)
    assert orphans == []


def test_parent_step_after_spawn_rescues_even_when_subagent_completed():
    # A live parent that reaped its subagent writes a follow-up step → never an orphan.
    parent = make_session("ses_parent", created=100_000_000)
    sub = make_session("ses_sub", parent="ses_parent", created=100_001_000)
    parts = [
        task_part("prt_task", "ses_parent", 100_000_000, "ses_sub"),
        make_part("prt_sf", "ses_sub", 100_060_000, "step-finish"),
        make_part("prt_parent_next", "ses_parent", 100_061_000, "text"),
    ]
    orphans = detect_orphans([parent, sub], parts, now_ms=100_400_000)
    assert orphans == []


def test_parent_silent_with_still_running_subagent_is_never_flagged():
    # Parent silent after spawn but the subagent is actively producing (recent parts,
    # no step-finish) → still running → not an orphan.
    parent = make_session("ses_parent", created=100_000_000)
    sub = make_session("ses_sub", parent="ses_parent", created=100_001_000, updated=100_390_000)
    parts = [
        task_part("prt_task", "ses_parent", 100_000_000, "ses_sub"),
        make_part("prt_ss", "ses_sub", 100_001_000, "step-start"),
        make_part("prt_reason", "ses_sub", 100_380_000, "reasoning"),
    ]
    orphans = detect_orphans([parent, sub], parts, now_ms=100_400_000)
    assert orphans == []


def test_parent_silent_subagent_crashed_is_detected_without_result():
    # No step-finish + silent past crash_grace → crashed zombie, result unavailable.
    parent = make_session("ses_parent", created=100_000_000)
    sub = make_session("ses_sub", parent="ses_parent", created=100_001_000, updated=100_010_000)
    parts = [
        task_part("prt_task", "ses_parent", 100_000_000, "ses_sub"),
        make_part("prt_ss", "ses_sub", 100_001_000, "step-start"),
    ]
    now = 100_001_000 + CRASH_GRACE_S * 1000 + 1000
    orphans = detect_orphans([parent, sub], parts, now_ms=now)
    assert len(orphans) == 1
    assert orphans[0].terminated_reason == "crashed"
    assert orphans[0].result_available is False


def test_heartbeat_compaction_after_spawn_does_not_rescue_the_parent():
    # Adversarial heartbeat evasion (p5): a NON-meaningful part (compaction — session
    # bookkeeping, not agent progress) after spawn must not count as a parent step.
    parent = make_session("ses_parent", created=100_000_000)
    sub = make_session("ses_sub", parent="ses_parent", created=100_001_000)
    parts = [
        task_part("prt_task", "ses_parent", 100_000_000, "ses_sub"),
        make_part("prt_sf", "ses_sub", 100_060_000, "step-finish"),
        make_part("prt_compact", "ses_parent", 100_200_000, "compaction"),
    ]
    orphans = detect_orphans([parent, sub], parts, now_ms=100_400_000)
    assert len(orphans) == 1
    assert orphans[0].terminated_reason == "completed"


def test_detection_is_deterministic_and_sorted():
    sessions, parts, now, _ = completed_subagent_scenario()
    first = detect_orphans(sessions, parts, now_ms=now)
    second = detect_orphans(sessions, parts, now_ms=now)
    assert [o.orphan_id for o in first] == [o.orphan_id for o in second]


def test_nested_delegation_duplicate_session_yields_each_orphan_once():
    # A session that is BOTH a subagent (of a root) AND a parent (of a further subagent)
    # is loaded once as a subagent and once as a parent — the store projection can hand the
    # detector the SAME session twice. The pure detection rule must still emit each
    # (parent, subagent) orphan exactly once (the live 50GB store exercises this: three
    # nested delegations each duplicated their record in one pass).
    root = make_session("ses_root", created=100_000_000)
    mid = make_session("ses_mid", parent="ses_root", created=100_001_000)
    leaf = make_session("ses_leaf", parent="ses_mid", created=100_002_000)
    # The projection-level duplication: ``mid`` handed in twice (once as subagent, once
    # as parent — mirroring SQLiteSessionStore._load_sessions returning subagents+parents).
    sessions = [root, mid, leaf, mid]
    parts = [
        task_part("prt_root_task", "ses_root", 100_000_000, "ses_mid"),
        task_part("prt_mid_task", "ses_mid", 100_002_000, "ses_leaf"),
        make_part("prt_leaf_finish", "ses_leaf", 100_003_000, "step-finish"),
        make_part("prt_leaf_text", "ses_leaf", 100_003_000, "text"),
    ]
    orphans = detect_orphans(sessions, parts, now_ms=100_400_000)

    assert len(orphans) == 2  # ses_mid orphaned under root, ses_leaf orphaned under mid
    assert [o.orphan_id for o in orphans] == sorted(o.orphan_id for o in orphans)
    assert len({o.orphan_id for o in orphans}) == 2  # no duplicate orphan_id


def test_detect_orphans_rejects_nonpositive_crash_grace():
    sessions, parts, now, _ = completed_subagent_scenario()
    with pytest.raises(ValueError):
        detect_orphans(sessions, parts, now_ms=now, crash_grace_s=0)


def test_dangling_parent_is_skipped():
    # A subagent whose parent is not in the observed set cannot have its silence verified.
    sub = make_session("ses_sub", parent="ses_missing", created=100_001_000)
    parts = [make_part("prt_sf", "ses_sub", 100_060_000, "step-finish")]
    orphans = detect_orphans([sub], parts, now_ms=100_400_000)
    assert orphans == []


def test_self_referential_parent_id_never_yields_a_self_orphan():
    # Adversarial p5 probe O3: a malformed row whose ``parent_id`` points at ITSELF (a top-level
    # session's parent is NULL — no session is its own delegation) must never be flagged as its
    # own orphan, even when it looks terminated (a spurious parent==subagent record would poison
    # the ledger with nonsense).
    malformed = make_session("ses_self", parent="ses_self", created=100_000_000, updated=100_060_000)
    parts = [
        make_part("prt_ss", "ses_self", 100_000_000, "step-start"),
        make_part("prt_sf", "ses_self", 100_060_000, "step-finish"),
    ]
    orphans = detect_orphans([malformed], parts, now_ms=100_400_000)
    assert orphans == []


# ── the terra-orphan REPLAY (the regression proof) ───────────────────────────


def _flat_model(model):
    if isinstance(model, dict):
        provider = model.get("providerID") or ""
        mid = model.get("id") or ""
        return f"{provider}/{mid}" if provider and mid else mid
    return str(model)


def _parse_iso(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def _load_terra_fixture():
    data = json.loads(FIXTURE.read_text())
    sessions = [
        SessionRecord(
            id=s["id"], parent_id=s["parent_id"], title=s["title"],
            model=_flat_model(s["model"]),
            time_created=s["time_created"], time_updated=s["time_updated"],
        )
        for s in data["sessions"]
    ]
    parts = [
        PartRecord(
            id=p["id"], session_id=p["session_id"], time_created=p["time_created"],
            type=p["type"], data=p.get("data", {}),
        )
        for p in data["parts"]
    ]
    return sessions, parts, _parse_iso(data["reconstructed_at_utc"])


def test_terra_orphan_is_replayed_and_detected():
    """The F1 43.4-minute stall reconstructed: parent f3 silent after the delegation, the
    pipeline-ops subagent completed, the result never reaped — the sweep flags it with the
    timestamp evidence at the moment the stall ended."""
    sessions, parts, now_ms = _load_terra_fixture()

    orphans = detect_orphans(sessions, parts, now_ms=now_ms)

    assert len(orphans) == 1
    orphan = orphans[0]
    # The exact sessions from the post-mortem's F1 evidence.
    assert orphan.parent_session_id == "ses_fc01d0331ffeKfHvCG2JjQWQvz"   # fork #3 (gpt-5.6-terra)
    assert orphan.subagent_session_id == "ses_fc016732fffeVJhTB45TH0uSbE"  # @pipeline-ops (deepseek)
    assert orphan.subagent_model == "deepseek/deepseek-v4-flash"
    # The delegation at 2026-08-26 21:11:02Z (23:11:02 local) and the subagent completion
    # at 21:12:31Z — with the parent having NO part after the spawn.
    assert orphan.spawn_at == "2026-08-26T21:11:02Z"
    assert orphan.parent_last_step_ms is None  # no meaningful part after spawn
    assert orphan.terminated_reason == "completed"
    assert orphan.result_available is True
    # Observed at the moment the stall ended (21:54:21Z) the completed result has sat
    # un-reaped for the measured ~41.8 minutes — the "dated, flagged event" the post-mortem
    # demanded ("stalls become dated, flagged events instead of anecdotes").
    assert orphan.idle_minutes >= 40.0
    assert orphan.idle_minutes < 45.0
    assert orphan.orphan_id == orphan_id(
        "ses_fc01d0331ffeKfHvCG2JjQWQvz", "ses_fc016732fffeVJhTB45TH0uSbE"
    )


# ── the full sweep cycle (observe → detect → reap → record → surface) ────────


class FakeRedis:
    """Record hot-list operations; optionally expose no pre-existing mapping."""

    def __init__(self):
        self.calls = []
        self.pushed = []

    def lpush(self, key, value):
        self.calls.append(("lpush", key, value))
        self.pushed.append(value)

    def ltrim(self, key, start, end):
        self.calls.append(("ltrim", key, start, end))

    def hget(self, key, field):
        return None


@pytest.fixture
def store_db(tmp_path):
    """A real SQLite session store (same tables/columns as opencode.db) seeded with the
    completed-subagent orphan scenario, returned as (path, expected_orphan_count)."""
    import sqlite3

    db = tmp_path / "opencode.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE session (
            id text PRIMARY KEY, parent_id text, title text NOT NULL,
            model text NOT NULL, time_created integer NOT NULL, time_updated integer NOT NULL
        );
        CREATE TABLE part (
            id text PRIMARY KEY, message_id text NOT NULL, session_id text NOT NULL,
            time_created integer NOT NULL, time_updated integer NOT NULL, data text NOT NULL
        );
        """
    )
    sessions, _, _, _ = completed_subagent_scenario()
    for s in sessions:
        conn.execute(
            "INSERT INTO session VALUES (?,?,?,?,?,?)",
            (s.id, s.parent_id, s.title, json.dumps({"providerID": "deepseek", "id": "deepseek-v4-flash"}),
             s.time_created, s.time_updated),
        )
    parts = [
        task_part("prt_task", "ses_parent", 100_000_000, "ses_sub"),
        make_part("prt_ss", "ses_sub", 100_001_000, "step-start"),
        make_part("prt_sf", "ses_sub", 100_060_000, "step-finish"),
    ]
    for i, p in enumerate(parts):
        conn.execute(
            "INSERT INTO part VALUES (?,?,?,?,?,?)",
            (p.id, f"msg_{i}", p.session_id, p.time_created, p.time_created, json.dumps(p.data)),
        )
    conn.commit()
    conn.close()
    return db, 1


def test_sweep_once_records_detects_reaps_and_deduplicates(store_db, tmp_path):
    db, expected = store_db
    ledger = tmp_path / "orphans.jsonl"
    redis_client = FakeRedis()
    store = SQLiteSessionStore(db)
    try:
        first = sweep_once(store, ledger_path=ledger, redis_client=redis_client, now_ms=100_400_000)
    finally:
        store.close()

    assert len(first) == expected
    assert first[0].subagent_session_id == "ses_sub"
    lines = ledger.read_text().splitlines()
    assert len(lines) == 1
    recorded = json.loads(lines[0])
    assert recorded["flagged"] is True
    assert recorded["orphan_id"] == first[0].orphan_id
    # Bounded Redis hot path carries the same canonical payload (dated, flagged, queryable).
    assert any(call[0] == "lpush" and call[1] == ORPHAN_EVENTS_KEY for call in redis_client.calls)
    assert any(call[0] == "ltrim" and call[1] == ORPHAN_EVENTS_KEY for call in redis_client.calls)

    # Second cycle: same orphan observed but NOT re-recorded (de-duplicated by orphan_id).
    store = SQLiteSessionStore(db)
    try:
        second = sweep_once(store, ledger_path=ledger, redis_client=redis_client, now_ms=100_500_000)
    finally:
        store.close()
    assert second == []
    assert len(ledger.read_text().splitlines()) == 1


def test_sqlite_session_store_skips_unrelated_sessions(store_db, tmp_path):
    """Only subagent + parent sessions are loaded — a big unrelated session never enters."""
    import sqlite3

    db, _ = store_db
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO session VALUES (?,?,?,?,?,?)",
        ("ses_unrelated", None, "Top-level solo", '{"providerID":"openai","id":"gpt-5.6-terra"}',
         200_000_000, 200_100_000),
    )
    conn.execute(
        "INSERT INTO part VALUES (?,?,?,?,?,?)",
        ("prt_uni", "msg_x", "ses_unrelated", 200_050_000, 200_050_000,
         json.dumps({"type": "text"})),
    )
    conn.commit()
    conn.close()

    store = SQLiteSessionStore(db)
    try:
        sessions, parts = store.load()
    finally:
        store.close()
    loaded = {s.id for s in sessions}
    assert "ses_unrelated" not in loaded
    assert "ses_parent" in loaded and "ses_sub" in loaded


# ── zombie reaping (the one allowed actuation) ───────────────────────────────


def test_reap_orphaned_subagents_sigterms_only_matching_processes(monkeypatch):
    import os
    import signal

    orphans, = _single_orphan()
    killed = []

    def _fake_kill(pid, sig):
        killed.append((pid, sig))

    monkeypatch.setattr(os, "kill", _fake_kill)
    table = {111: "opencode run --session ses_unrelated", 222: "opencode run --session ses_sub"}
    reaped = reap_orphaned_subagents([orphans], process_table=table)

    assert reaped == {"ses_sub": [222]}
    assert killed == [(222, signal.SIGTERM)]
    assert 111 not in [pid for pid, _ in killed]


def test_reap_orphaned_subagents_no_match_no_kill():
    orphans, = _single_orphan()
    reaped = reap_orphaned_subagents([orphans], process_table={111: "unrelated"})
    assert reaped == {}


def _single_orphan():
    sessions, parts, now, _ = completed_subagent_scenario()
    return detect_orphans(sessions, parts, now_ms=now)


# ── ledger + registry emission ───────────────────────────────────────────────


def test_record_orphan_lands_durable_jsonl_then_redis_then_registry(monkeypatch, tmp_path):
    """Mirrors test_emit_flag: durable JSONL first, bounded hot list second, and the
    FINOPS_KB_WRITE-gated canonical registration last — all in one dated, flagged record."""
    orphans, = _single_orphan()
    ledger = tmp_path / "orphans.jsonl"
    redis_client = FakeRedis()
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")

    published = []
    monkeypatch.setattr(ks, "register_records", lambda records, fail_loud=False: published.extend(records) or [])

    record_orphan(orphans, ledger_path=ledger, redis_client=redis_client)

    persisted = json.loads(ledger.read_text())
    pushed = redis_client.pushed[0]
    assert json.loads(pushed) == persisted
    assert persisted["orphan_id"] == orphans.orphan_id
    assert persisted["flagged"] is True
    assert persisted["detected_at"].endswith("Z")
    assert ("ltrim", ORPHAN_EVENTS_KEY, 0, 199) in redis_client.calls
    # Registry record: source_type=orphan, MEASURED (deterministic detection, not [H]).
    assert len(published) == 1
    assert published[0].source_type == "orphan"
    assert published[0].evidence_class == "[M]"


def test_record_orphan_keeps_durable_write_when_registry_or_redis_down(monkeypatch, tmp_path):
    orphans, = _single_orphan()
    ledger = tmp_path / "orphans.jsonl"
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")
    monkeypatch.setattr(
        ks, "register_records", lambda records, fail_loud=False: (_ for _ in ()).throw(RuntimeError("db2 down"))
    )

    class _DownRedis:
        def lpush(self, *a):
            raise RuntimeError("redis down")

        def ltrim(self, *a):
            raise RuntimeError("redis down")

    record_orphan(orphans, ledger_path=ledger, redis_client=_DownRedis())

    assert json.loads(ledger.read_text())["orphan_id"] == orphans.orphan_id


def test_record_orphan_skips_registry_when_kb_write_unset(monkeypatch, tmp_path):
    orphans, = _single_orphan()
    monkeypatch.delenv("FINOPS_KB_WRITE", raising=False)

    def _explode(*a, **k):
        raise AssertionError("must not register when FINOPS_KB_WRITE is unset")

    monkeypatch.setattr(ks, "register_records", _explode)
    record_orphan(orphans, ledger_path=tmp_path / "orphans.jsonl")
    # No AssertionError raised == no registration attempt.


def test_load_recorded_orphan_ids_reads_existing_ledger(tmp_path):
    orphans, = _single_orphan()
    ledger = tmp_path / "orphans.jsonl"
    ledger.write_text(json.dumps({"orphan_id": "abc123"}) + "\nnot-json\n")
    assert load_recorded_orphan_ids(ledger) == {"abc123"}
    assert load_recorded_orphan_ids(tmp_path / "missing.jsonl") == set()


# ── flag-only structural guard ───────────────────────────────────────────────


def test_sweep_module_has_no_steering_surface():
    """Hard rule 2: the sweep is observation + reaping, never control. No opencode client
    import and no steering call anywhere in the CODE (the docstring documents the guarantee
    with those words; the AST scan proves the code itself never calls them)."""
    import ast

    import agentic_dynamics.control.orphan_sweep as osweep

    tree = ast.parse(Path(osweep.__file__).read_text())

    steering_names = {"send_input", "interrupt", "resume", "restart"}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in steering_names
        ):
            pytest.fail(f"orphan_sweep calls {node.func.attr!r} — a steering surface")
    # No opencode client is imported or referenced.
    source = Path(osweep.__file__).read_text()
    for forbidden in ("opencode_client", "OpenCodeClient", "OpenCodeError"):
        assert forbidden not in source, f"orphan_sweep must not reference {forbidden!r}"
    # The only process-mutation primitive is SIGTERM reaping of already-terminated subagents.
    for allowed in ("signal.SIGTERM", "os.kill"):
        assert allowed in source


def test_cli_resolves_supervise_orphans():
    from agentic_dynamics import cli

    script, rest = cli._resolve(["supervise", "orphans"])
    assert script == "orphan_sweep.py"
    assert rest == []
    assert (cli._SCRIPTS_DIR / script).exists()


# ── the daemon script runs (the p1 live smoke) ───────────────────────────────


def _scripts_dir():
    return Path(__file__).resolve().parent.parent / "scripts"


def test_daemon_script_imports_and_runs_help():
    """The daemon resolves the package standalone — regression for the missing
    ``_bootstrap`` sys.path wiring (ModuleNotFoundError on ``python scripts/orphan_sweep.py``
    even for ``--help``)."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, str(_scripts_dir() / "orphan_sweep.py"), "--help"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "Server-level orphan sweep" in result.stdout
    assert "--once" in result.stdout


def test_daemon_once_smoke_detects_and_records(store_db, tmp_path):
    """The full CLI daemon (not just the library): one ``--once`` pass over a real
    session store detects the orphan and lands the dated, flagged record on the ledger."""
    import os
    import subprocess
    import sys

    db, _ = store_db
    ledger = tmp_path / "orphans.jsonl"
    env = dict(os.environ, FINOPS_KB_WRITE="", FINOPS_REDIS_PORT="6399")
    result = subprocess.run(
        [
            sys.executable, str(_scripts_dir() / "orphan_sweep.py"), "--once",
            "--db", str(db), "--ledger", str(ledger), "--crash-grace", "300",
        ],
        capture_output=True, text=True, timeout=120, env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "[ORPHAN] ses_sub" in result.stdout
    recorded = json.loads(ledger.read_text())
    assert recorded["subagent_session_id"] == "ses_sub"
    assert recorded["flagged"] is True
    assert recorded["detected_at"].endswith("Z")
