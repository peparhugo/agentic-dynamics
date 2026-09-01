"""Tests for the docs-drift watchdog — the cadence + observation rail (automatic_docs_sync p2).

The scanner's own correctness is ``tests/test_scan_docs_drift.py``'s job. These tests cover the
*rail*: given a report, does the flag lifecycle behave — raised by a finding, cleared by a clean
scan, silent on a repeat, and never cleared by a scan that could not look?

Reports are constructed directly rather than scanned. A real seven-axis scan takes minutes and
depends on the tree's current drift, which would make these tests both slow and non-hermetic;
the lifecycle is a pure function of the score, so injecting the score tests exactly the logic
under test. ``test_lifecycle_end_to_end_against_the_real_tree`` closes the loop with a genuine
scan of a subset of axes.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _watchdog():
    """Import the watchdog the way a direct ``python scripts/…`` run would."""
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    return importlib.import_module("docs_drift_watchdog")


def _scanner():
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    return importlib.import_module("scan_docs_drift")


def _report(*, findings: int = 0, errors: dict | None = None):
    """Build a DriftReport with ``findings`` stale anchor rows and one current row.

    The current row matters: it makes the report look like a real scan (something was checked)
    rather than an empty one, so a zero-drift assertion is distinguishable from "nothing ran".
    """
    s = _scanner()
    report = s.DriftReport()
    report.add(
        s.Check(
            check_id="anchor_integrity/anchor/ok",
            axis="anchor_integrity",
            claim="ARCHITECTURE.md:1 cites `README.md:1`",
            code_truth="README.md has >= 1 lines",
            status="current",
            basis="wc -l README.md",
            source="ARCHITECTURE.md:1",
        )
    )
    for i in range(findings):
        report.add(
            s.Check(
                check_id=f"anchor_integrity/anchor/stale-{i}",
                axis="anchor_integrity",
                claim=f"docs/x.md:{i} cites `apps/control_room/server.py:9999`",
                code_truth="line 9999 is past EOF",
                status="stale",
                basis="wc -l apps/control_room/server.py",
                source=f"docs/x.md:{i}",
            )
        )
    report.errors = dict(errors or {})
    return report


class _FakeRedis:
    """Minimal stand-in covering exactly the calls the watchdog's mirrors make."""

    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}

    def set(self, key: str, value: str) -> None:
        self.kv[key] = value

    def get(self, key: str) -> str | None:
        return self.kv.get(key)

    def lpush(self, key: str, *values: str) -> int:
        self.lists.setdefault(key, [])
        for v in values:
            self.lists[key].insert(0, v)
        return len(self.lists[key])

    def ltrim(self, key: str, start: int, end: int) -> None:
        self.lists[key] = self.lists.get(key, [])[start : end + 1]

    def ping(self) -> bool:
        return True


def _lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


# ─────────────────────────────────────────────────────────────────────────────────────────────
# The flag lifecycle — the phase's VERIFY contract, both directions
# ─────────────────────────────────────────────────────────────────────────────────────────────


def test_a_finding_raises_the_flag(tmp_path):
    """Direction 1: a scan with findings raises the flag from a clean slate."""
    w = _watchdog()
    r = _FakeRedis()

    result = w.run_once(report=_report(findings=3), results_dir=tmp_path, client=r)

    assert result.prior_state == w.STATE_CLEAR
    assert result.state == w.STATE_RAISED
    assert result.transition == "raised"
    assert result.drift == 3

    # Durable: the state file is the authority, and one transition line was appended.
    state = json.loads((tmp_path / w.STATE_FILE).read_text())
    assert state["state"] == w.STATE_RAISED
    flags = _lines(tmp_path / w.FLAGS_FILE)
    assert len(flags) == 1
    assert flags[0]["transition"] == "raised"
    assert flags[0]["status"] == w.STATUS_RAISED
    assert flags[0]["drift"] == 3
    # The inventory rides along with the durable line.
    assert len(flags[0]["inventory"]) == 3

    # Live mirrors.
    assert json.loads(r.kv[w.DRIFT_FLAG_KEY])["state"] == w.STATE_RAISED
    assert json.loads(r.kv[w.DOCS_DRIFT_BOARD_KEY])["health"] == "yellow"


def test_a_clean_scan_clears_a_raised_flag(tmp_path):
    """Direction 2: a subsequent clean scan clears the flag it raised. The lifecycle closes."""
    w = _watchdog()
    r = _FakeRedis()

    w.run_once(report=_report(findings=2), results_dir=tmp_path, client=r)
    result = w.run_once(report=_report(findings=0), results_dir=tmp_path, client=r)

    assert result.prior_state == w.STATE_RAISED
    assert result.state == w.STATE_CLEAR
    assert result.transition == "cleared"
    assert result.drift == 0

    assert json.loads((tmp_path / w.STATE_FILE).read_text())["state"] == w.STATE_CLEAR
    flags = _lines(tmp_path / w.FLAGS_FILE)
    assert [f["transition"] for f in flags] == ["raised", "cleared"]
    assert flags[-1]["status"] == w.STATUS_CLEARED
    assert json.loads(r.kv[w.DOCS_DRIFT_BOARD_KEY])["health"] == "green"


def test_a_repeated_finding_does_not_re_raise(tmp_path):
    """Edge-triggering: an unchanged finding rewrites the level surfaces but appends no flag.

    This is what makes an hourly cadence tolerable — a week of unfixed drift is one flag, not 168.
    """
    w = _watchdog()
    r = _FakeRedis()

    w.run_once(report=_report(findings=2), results_dir=tmp_path, client=r)
    second = w.run_once(report=_report(findings=2), results_dir=tmp_path, client=r)

    assert second.state == w.STATE_RAISED
    assert second.transition is None
    assert len(_lines(tmp_path / w.FLAGS_FILE)) == 1, "a repeat must not append a flag record"
    # ...but the trend line and the board row are level: both passes are recorded.
    assert len(_lines(tmp_path / w.HISTORY_FILE)) == 2
    assert w.DOCS_DRIFT_BOARD_KEY in r.kv


def test_since_is_carried_across_a_repeat_and_reset_on_a_transition(tmp_path):
    """``since`` answers "how long has this held?" — it must survive repeats and reset on edges."""
    w = _watchdog()

    first = w.run_once(report=_report(findings=1), results_dir=tmp_path, use_redis=False)
    repeat = w.run_once(report=_report(findings=1), results_dir=tmp_path, use_redis=False)
    cleared = w.run_once(report=_report(findings=0), results_dir=tmp_path, use_redis=False)

    assert repeat.board_row["since"] == first.board_row["since"]
    assert cleared.board_row["since"] == cleared.at != first.board_row["since"]


# ─────────────────────────────────────────────────────────────────────────────────────────────
# "Could not measure" is not "clean"
# ─────────────────────────────────────────────────────────────────────────────────────────────


def test_an_unmeasured_scan_never_clears_a_raised_flag(tmp_path):
    """A flag is retired by positive evidence, never by the absence of evidence."""
    w = _watchdog()

    w.run_once(report=_report(findings=4), results_dir=tmp_path, use_redis=False)
    result = w.run_once(
        report=_report(findings=0, errors={"anchor_integrity": "unreadable index"}),
        results_dir=tmp_path,
        use_redis=False,
    )

    assert result.state == w.STATE_RAISED, "an errored scan must not clear the flag"
    assert result.transition is None
    assert len(_lines(tmp_path / w.FLAGS_FILE)) == 1


def test_an_unmeasured_scan_does_not_raise_from_clear(tmp_path):
    """Symmetrically, an inability to scan is a SERVICE failure, not a docs-drift finding."""
    w = _watchdog()

    result = w.run_once(
        report=_report(findings=0, errors={"cli_surface": "boom"}),
        results_dir=tmp_path,
        use_redis=False,
    )

    assert result.state == w.STATE_CLEAR
    assert result.transition is None
    assert _lines(tmp_path / w.FLAGS_FILE) == []


def test_decide_state_maps_the_three_outcomes():
    """The state decision is a pure function — pin all three branches."""
    w = _watchdog()
    assert w.decide_state(_report(findings=0)) == w.STATE_CLEAR
    assert w.decide_state(_report(findings=1)) == w.STATE_RAISED
    assert w.decide_state(_report(findings=0, errors={"x": "y"})) == w.STATE_UNMEASURED
    # An errored scan that ALSO found drift is still unmeasured: a partial count is not a count.
    assert w.decide_state(_report(findings=3, errors={"x": "y"})) == w.STATE_UNMEASURED


# ─────────────────────────────────────────────────────────────────────────────────────────────
# The observation rail + the board row
# ─────────────────────────────────────────────────────────────────────────────────────────────


def test_the_flag_line_derives_a_valid_observation_record(tmp_path):
    """The line's projection must satisfy ``build_flag_record`` — the rail's actual contract."""
    pytest.importorskip("agentic_dynamics.control.observation_ingestion")
    from agentic_dynamics.control.observation_ingestion import (
        SOURCE_TYPE_FLAG,
        derive_flag_record,
    )

    w = _watchdog()
    line = w.build_flag_line(_report(findings=2), transition="raised")
    record = derive_flag_record(line)

    assert record.source_type == SOURCE_TYPE_FLAG
    assert record.evidence_class == "[H]"
    # Stable subject identity: raise and clear are versions of ONE entity, which is the lifecycle.
    cleared = derive_flag_record(w.build_flag_line(_report(), transition="cleared"))
    assert cleared.entity_id == record.entity_id


def test_the_inventory_is_bounded_on_the_durable_line():
    """A badly-drifted tree must not produce an unreadable JSONL line; the report holds the rest."""
    w = _watchdog()
    line = w.build_flag_line(_report(findings=60), transition="raised", inventory_limit=10)
    assert len(line["inventory"]) == 10
    assert line["inventory_truncated"] == 50
    assert line["report"].endswith("latest.json"), "the full evidence must be named"


def test_the_board_row_maps_state_to_the_panel_colours():
    """green / yellow / red is computed once, here — not re-derived in the browser."""
    w = _watchdog()
    green = w.build_board_row(_report(), state=w.STATE_CLEAR, since="t")
    yellow = w.build_board_row(_report(findings=1), state=w.STATE_RAISED, since="t")
    red = w.build_board_row(
        _report(errors={"x": "y"}), state=w.STATE_UNMEASURED, since="t"
    )
    assert (green["health"], yellow["health"], red["health"]) == ("green", "yellow", "red")
    # The p3 gate owns proposal_state; the watchdog declares it and proposes nothing.
    assert green["proposal_state"] == "none"


def test_the_board_row_is_merged_into_the_fleet_board(tmp_path):
    """The row must reach ``fleet:board`` through fleet_manager's merge, not by writing it."""
    w = _watchdog()
    fleet_dir = str(ROOT / "scripts" / "fleet")
    if fleet_dir not in sys.path:
        sys.path.insert(0, fleet_dir)
    fm = importlib.import_module("fleet_manager")

    r = _FakeRedis()
    # The watchdog and the board watcher agree on the key without sharing a constant by import.
    assert w.DOCS_DRIFT_BOARD_KEY == fm.DOCS_DRIFT_KEY

    w.run_once(report=_report(findings=2), results_dir=tmp_path, client=r)
    row = fm._docs_drift_row(r)
    assert row["state"] == w.STATE_RAISED
    assert row["drift"] == 2


def test_the_board_row_reader_reports_absent_rather_than_fabricating_clean():
    """No scan must never render as a clean scan."""
    fleet_dir = str(ROOT / "scripts" / "fleet")
    if fleet_dir not in sys.path:
        sys.path.insert(0, fleet_dir)
    fm = importlib.import_module("fleet_manager")

    assert fm._docs_drift_row(_FakeRedis()) == {}

    class _Corrupt(_FakeRedis):
        def get(self, key):
            return "{not json"

    assert fm._docs_drift_row(_Corrupt()) == {}


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Persistence, degradation, CLI
# ─────────────────────────────────────────────────────────────────────────────────────────────


def test_dry_run_writes_nothing(tmp_path):
    w = _watchdog()
    result = w.run_once(report=_report(findings=2), results_dir=tmp_path, dry_run=True)
    assert result.transition == "raised", "the would-be transition is still reported"
    assert result.written == []
    assert list(tmp_path.iterdir()) == []


def test_the_durable_writes_survive_a_downed_redis(tmp_path):
    """File is the truth; Redis is the mirror. A blip costs the live surface, not the record."""
    w = _watchdog()

    class _Down(_FakeRedis):
        def set(self, key, value):
            raise RuntimeError("redis is down")

        def lpush(self, key, *values):
            raise RuntimeError("redis is down")

    result = w.run_once(report=_report(findings=1), results_dir=tmp_path, client=_Down())

    assert result.transition == "raised"
    assert json.loads((tmp_path / w.STATE_FILE).read_text())["state"] == w.STATE_RAISED
    assert len(_lines(tmp_path / w.FLAGS_FILE)) == 1


def test_prior_state_is_read_from_the_file_not_redis(tmp_path):
    """A flushed Redis must not look like "the flag was never raised" and re-notify the operator."""
    w = _watchdog()
    r = _FakeRedis()
    w.run_once(report=_report(findings=2), results_dir=tmp_path, client=r)

    r.kv.clear()  # simulate a Redis restart / flush
    second = w.run_once(report=_report(findings=2), results_dir=tmp_path, client=r)

    assert second.prior_state == w.STATE_RAISED
    assert second.transition is None, "the flag was already known — do not re-raise"


def test_a_corrupt_state_file_degrades_to_the_clean_slate(tmp_path):
    """A broken memory must not stop the watchdog measuring."""
    w = _watchdog()
    (tmp_path / w.STATE_FILE).write_text("{ this is not json")
    assert w.read_flag_state(tmp_path)["state"] == w.STATE_CLEAR


def test_latest_json_is_the_report_shape_the_gate_and_panel_read(tmp_path):
    w = _watchdog()
    w.run_once(report=_report(findings=2), results_dir=tmp_path, use_redis=False)
    payload = json.loads((tmp_path / w.LATEST_FILE).read_text())
    assert payload["schema"] == "docs-drift/v1"
    assert payload["score"]["drift"] == 2
    assert len(payload["findings"]) == 2


def test_history_records_every_pass_including_clean_ones(tmp_path):
    """The trend needs the clean passes too — "clean for a week" is a fact worth having."""
    w = _watchdog()
    for findings in (0, 0, 1, 0):
        w.run_once(report=_report(findings=findings), results_dir=tmp_path, use_redis=False)
    history = _lines(tmp_path / w.HISTORY_FILE)
    assert [h["drift"] for h in history] == [0, 0, 1, 0]
    assert [h["transition"] for h in history] == [None, None, "raised", "cleared"]


def test_main_exit_codes(tmp_path, monkeypatch):
    """0 whether clean or drifting; 1 only under --fail-on-drift; 2 when the scan could not run."""
    w = _watchdog()

    monkeypatch.setattr(w.scan_docs_drift, "scan", lambda axes: _report(findings=0))
    assert w.main(["--results-dir", str(tmp_path), "--no-redis"]) == 0

    monkeypatch.setattr(w.scan_docs_drift, "scan", lambda axes: _report(findings=3))
    # Drift alone is NOT a unit failure — finding drift is the rail succeeding.
    assert w.main(["--results-dir", str(tmp_path), "--no-redis"]) == 0
    assert w.main(["--results-dir", str(tmp_path), "--no-redis", "--fail-on-drift"]) == 1

    monkeypatch.setattr(
        w.scan_docs_drift, "scan", lambda axes: _report(findings=0, errors={"x": "unreadable"})
    )
    assert w.main(["--results-dir", str(tmp_path), "--no-redis"]) == 2


# ─────────────────────────────────────────────────────────────────────────────────────────────
# The loop closed against the real tree
# ─────────────────────────────────────────────────────────────────────────────────────────────


def test_lifecycle_end_to_end_against_the_real_tree(tmp_path):
    """A genuine scan drives both directions — no injected report anywhere in this test.

    ``status_vocabulary`` + ``spec_lifecycle`` are clean on this tree, so scanning them is a real
    clean scan; ``anchor_integrity`` carries the tree's real stale anchors, so scanning it is a
    real finding. Raising then clearing across the two proves the rail end-to-end on real data.
    """
    w = _watchdog()
    s = _scanner()

    drifting = s.scan(("anchor_integrity",))
    if drifting.errors or drifting.score()["drift"] == 0:
        pytest.skip("anchor_integrity is clean or errored on this tree — nothing to raise with")

    raised = w.run_once(report=drifting, results_dir=tmp_path, use_redis=False)
    assert raised.transition == "raised"

    clean = s.scan(("spec_lifecycle", "status_vocabulary"))
    if clean.errors or clean.score()["drift"] != 0:
        pytest.skip("the reference clean axes are not clean on this tree")

    cleared = w.run_once(report=clean, results_dir=tmp_path, use_redis=False)
    assert cleared.transition == "cleared"
    assert [f["transition"] for f in _lines(tmp_path / w.FLAGS_FILE)] == ["raised", "cleared"]


def test_the_flag_producer_writes_the_artifact_its_pointer_names(tmp_path, monkeypatch):
    """The event is a POINTER: the bytes it hashes must exist before the pointer is published.

    This is the step ``scripts/supervise.py:emit_flag`` omits — which is why no ``source_type=flag``
    record had ever materialised in the registry index. Registering a pointer to a file that is
    never written produces a record the consumer cannot verify and must dead-letter, so the flag
    would be "registered" and still unqueryable.
    """
    pytest.importorskip("agentic_dynamics.knowledge.knowledge_ingestion")
    import hashlib

    from agentic_dynamics.control.observation_ingestion import derive_flag_record
    from agentic_dynamics.knowledge import knowledge_ingestion as ki

    w = _watchdog()
    published: list = []

    # Redirect the artifact directory into tmp_path, and capture the publish instead of
    # requiring a live DB2 stream — this test is about the write, not the transport.
    monkeypatch.setattr(w, "ROOT", tmp_path)
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")
    monkeypatch.setattr(
        "agentic_dynamics.knowledge.knowledge_stream.register_records",
        lambda records, *, fail_loud: published.extend(records) or [],
    )

    line = w.build_flag_line(_report(findings=2), transition="raised")
    assert w.register_flag_record(line) is True
    assert len(published) == 1

    record = derive_flag_record(line)
    artifact = tmp_path / "experiments" / "results" / "kb" / f"{record.knowledge_id}.json"
    assert artifact.exists(), "the pointer's target must exist before the pointer is published"

    # The hash the event advertises must cover exactly the bytes on disk, or the consumer
    # rejects the record.
    event = ki.record_to_event(record)
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == event.content_hash
    assert event.source_uri.endswith(f"{record.knowledge_id}.json")


def test_the_kb_write_is_opt_in(tmp_path, monkeypatch):
    """Without FINOPS_KB_WRITE=1 the rail writes nothing to the knowledge plane."""
    w = _watchdog()
    monkeypatch.setattr(w, "ROOT", tmp_path)
    monkeypatch.delenv("FINOPS_KB_WRITE", raising=False)
    assert w.register_flag_record(w.build_flag_line(_report(findings=1), transition="raised")) is False
    assert not (tmp_path / "experiments").exists()
