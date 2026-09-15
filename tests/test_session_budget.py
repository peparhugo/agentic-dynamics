"""Session-budget tests — ``session-budget/v2`` (capacity-derived policy, 2026-09-15).

The operator's context-policy change: the AIO's context management judges against the ACTIVE
session model's resolved capacity (the ported opencode 1.18.15 calculation), NOT a universal
constant; the 80% warning is ADVISORY; message count is TELEMETRY (never a stopping
condition); at the usable boundary the native runtime compacts and the session continues;
CLOSE is reserved for the hard model context limit. The negative half is unchanged: an
unreadable budget is UNJUDGED — never silently OK, exactly as an unknown cost is never zero.

Every test is hermetic: the catalog is a tmp fixture (``FINOPS_OPENCODE_MODELS_CACHE``), the
runtime config roots are tmp (``XDG_CONFIG_HOME``), and the session db is synthetic with the
real opencode shape (session.model + per-message tokens).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from agentic_dynamics.core import session_capacity as sc
from scripts.session_budget import (
    SCHEMA_ID,
    SESSION_ID_ENV,
    _measure,
    _resolve_session_id,
    _session_exists,
    main,
    measure_verdict,
)

FLASH = {"providerID": "deepseek", "id": "deepseek-v4-flash", "variant": "max"}
MID = {"providerID": "midco", "id": "mid-model"}
SMALL = {"providerID": "smallco", "id": "small-model"}

CATALOG = {
    "deepseek": {
        "models": {"deepseek-v4-flash": {"limit": {"context": 1_000_000, "output": 384_000}}}
    },
    "midco": {"models": {"mid-model": {"limit": {"context": 200_000, "output": 8_000}}}},
    "smallco": {"models": {"small-model": {"limit": {"context": 160_000, "output": 8_000}}}},
}


def _catalog(tmp_path: Path) -> Path:
    path = tmp_path / "models.json"
    path.write_text(json.dumps(CATALOG), encoding="utf-8")
    return path


def _hermetic(tmp_path: Path, monkeypatch) -> Path:
    """Point the resolver at tmp-only catalog/config roots (no host config can leak in)."""
    cache = _catalog(tmp_path)
    monkeypatch.setenv(sc.MODELS_CACHE_ENV, str(cache))
    config_home = tmp_path / "config-home"
    config_home.mkdir(exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("FINOPS_SESSION_BUDGET_JOURNAL", str(tmp_path / "budget.jsonl"))
    return cache


def _make_session_db(
    path: Path,
    *,
    turns: int,
    context: int,
    sid: str = "ses_judged",
    model: dict | None = FLASH,
    directory: str = "/nonexistent/project",
) -> str:
    """A synthetic opencode-shaped session db: the judged session plus an OLDER sibling."""
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE session (id TEXT, time_updated INTEGER, model TEXT, version TEXT, directory TEXT)")
    con.execute("CREATE TABLE message (session_id TEXT, time_created INTEGER, data TEXT)")
    con.execute(
        "INSERT INTO session VALUES (?, ?, ?, ?, ?)",
        (sid, 200, json.dumps(model) if model else None, "1.18.15", directory),
    )
    con.execute(
        "INSERT INTO session VALUES (?, ?, ?, ?, ?)",
        ("ses_old", 100, json.dumps(model) if model else None, "1.18.15", directory),
    )
    for i in range(max(0, turns - 1)):
        con.execute(
            "INSERT INTO message VALUES (?, ?, ?)",
            (sid, i, json.dumps({"role": "assistant", "tokens": {"total": 10, "input": 10}})),
        )
    if turns >= 1:
        # The LAST assistant message carries the live context size (the runtime's measure).
        con.execute(
            "INSERT INTO message VALUES (?, ?, ?)",
            (sid, turns, json.dumps({"role": "assistant", "tokens": {"total": context, "input": context}})),
        )
        con.execute(
            "INSERT INTO message VALUES (?, ?, ?)",
            (sid, turns + 1, json.dumps({"role": "user", "tokens": {"input": 5}})),
        )
    con.commit()
    con.close()
    return sid


def _set_model(path: Path, sid: str, model: dict | None) -> None:
    con = sqlite3.connect(path)
    con.execute("UPDATE session SET model=? WHERE id=?", (json.dumps(model) if model else None, sid))
    con.commit()
    con.close()


def _append_compaction_summary(path: Path, sid: str, *, summary_tokens: int = 15_000) -> None:
    """A compaction summary message (opencode marks it a summary; the context drops)."""
    con = sqlite3.connect(path)
    con.execute(
        "INSERT INTO message VALUES (?, ?, ?)",
        (sid, 99_000, json.dumps(
            {"role": "assistant", "summary": True,
             "tokens": {"total": summary_tokens, "input": summary_tokens}}
        )),
    )
    con.commit()
    con.close()


def _add_unfinished_assistant_message(path: Path, sid: str, *, zero_valued: bool = False) -> None:
    """Append a STREAMING assistant message after the completed samples.

    ``zero_valued=True`` writes the REAL OpenCode pending shape (Astra finding, 2026-09-14):
    the usage fields EXIST and are initialized to ZERO before the turn finalizes. The check
    must treat that exactly like the absent-fields shape — an unfinished sample, never a
    valid zero reading.
    """
    if zero_valued:
        payload = {"role": "assistant",
                   "tokens": {"total": 0, "input": 0, "output": 0, "reasoning": 0,
                              "cache": {"read": 0, "write": 0}}}
    else:
        payload = {"role": "assistant"}
    con = sqlite3.connect(path)
    con.execute(
        "INSERT INTO message VALUES (?, ?, ?)",
        (sid, 9000, json.dumps(payload)),
    )
    con.commit()
    con.close()


def _add_younger_child_session(path: Path, sid: str) -> str:
    """A NEWER child session (updated after the judged one) — the row a most-recently-updated
    fallback would wrongly pick."""
    con = sqlite3.connect(path)
    con.execute(
        "INSERT INTO session VALUES (?, ?, ?, ?, ?)",
        ("ses_child_newer", 300, json.dumps(FLASH), "1.18.15", "/nonexistent/project"),
    )
    con.execute(
        "INSERT INTO message VALUES (?, ?, ?)",
        ("ses_child_newer", 0, json.dumps({"role": "assistant", "tokens": {"total": 1, "input": 1}})),
    )
    con.commit()
    con.close()
    return "ses_child_newer"


# ── the installed runtime's calculation (ported formula) ────────────────────────


def test_the_formula_is_the_installed_runtimes_own():
    """opencode 1.18.15: maxOutputTokens = min(limit.output, 32000) || 32000; usable =
    context - maxOutputTokens when no input limit, input - reserved when there is one."""
    assert sc.max_output_tokens(384_000) == 32_000  # capped by OUTPUT_TOKEN_MAX
    assert sc.max_output_tokens(8_000) == 8_000  # a smaller model's own ceiling
    assert sc.max_output_tokens(None) == 32_000  # `|| Z` — never zero
    assert sc.max_output_tokens(0) == 32_000

    deepseek = sc.effective_limit(
        context_limit=1_000_000, input_limit=None, output_limit=384_000
    )
    assert deepseek == 968_000  # 1M - 32K response headroom
    openai_shaped = sc.effective_limit(
        context_limit=1_050_000, input_limit=922_000, output_limit=128_000
    )
    assert openai_shaped == 902_000  # 922K input - min(20000, 32000) reserve
    reserved = sc.effective_limit(
        context_limit=1_050_000, input_limit=922_000, output_limit=128_000, reserved=15_000
    )
    assert reserved == 907_000  # the config's compaction.reserved wins for input-limit models


def test_the_measure_is_the_runtimes_overflow_measure():
    assert sc.usage_context_tokens({"total": 123}) == 123
    assert sc.usage_context_tokens({"input": 1, "output": 2, "cache": {"read": 3, "write": 4}}) == 10
    assert sc.usage_context_tokens({"total": 0, "input": 0, "cache": {"read": 0}}) is None
    assert sc.usage_context_tokens({}) is None


# ── the operator's verifications ────────────────────────────────────────────────


def test_172491_passes_for_the_active_model_when_within_capacity(tmp_path, monkeypatch):
    """The exact reading that was refused at the old 200K policy now PASSES: the active model
    (deepseek-v4-flash: 1M context, 32K response headroom → 968K usable) is the limit."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=35, context=172_491)
    verdict, reason, measured = measure_verdict(sid, db_path=db)
    assert measured is True
    assert verdict == "OK", reason
    assert main(["--db", str(db), "--session-id", sid, "--json", "--no-journal"]) == 0


def test_more_than_80_low_context_messages_never_forces_closure(tmp_path, monkeypatch):
    """Message count is TELEMETRY: 120 assistant messages at 50K context is OK (the old
    80-turn stopping condition is removed)."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=120, context=50_000)
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "OK", reason
    capacity, _, _ = sc.resolve_capacity(db, sid)
    assert capacity is not None and capacity.effective_limit == 968_000


def test_switching_to_a_smaller_model_updates_the_limit(tmp_path, monkeypatch):
    """The capacity follows the model recorded on the SESSION row (never the repo default)."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=35, context=172_491, model=FLASH)
    assert measure_verdict(sid, db_path=db)[0] == "OK"

    _set_model(db, sid, MID)  # 200K context, 8K output → 192K usable → advisory zone
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "WARN", reason
    assert "advisory" in reason

    _set_model(db, sid, SMALL)  # 160K context → 172,491 is past the HARD limit
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "CLOSE", reason


def test_compaction_permits_continuation_under_the_same_session(tmp_path, monkeypatch):
    """At the usable boundary the runtime compacts natively: the verdict is COMPACT (never
    CLOSE), and after the summary message the SAME session measures OK again."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=60, context=970_000)
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "COMPACT", reason
    assert "compacts natively" in reason and "continues" in reason

    _append_compaction_summary(db, sid)
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "OK", reason
    assert _session_exists(db, sid)  # the same session identity — continuity preserved


def test_missing_identity_is_a_refusal_not_a_guess(tmp_path, monkeypatch):
    """No --session-id and no FINOPS_SESSION_ID → UNJUDGED with the named reason; the check
    never picks the globally most recently updated session."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000)
    _add_younger_child_session(db, sid)
    monkeypatch.delenv(SESSION_ID_ENV, raising=False)
    rc = main(["--db", str(db), "--json"])
    assert rc == 1
    journal = (tmp_path / "budget.jsonl").read_text(encoding="utf-8").strip().splitlines()
    entry = json.loads(journal[-1])
    assert entry["verdict"] == "UNJUDGED"
    assert "no session identity supplied" in entry["reason"]


def test_an_invalid_session_id_is_rejected(tmp_path, monkeypatch):
    """A nonexistent id is UNJUDGED with the named reason — never a fallback to some other
    row, never a (0, 0) reading that reads as an empty-but-valid session."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    _make_session_db(db, turns=5, context=30_000)
    rc = main(["--db", str(db), "--session-id", "ses_nonexistent", "--json"])
    assert rc == 1
    journal = (tmp_path / "budget.jsonl").read_text(encoding="utf-8").strip().splitlines()
    entry = json.loads(journal[-1])
    assert entry["verdict"] == "UNJUDGED"
    assert "does not exist" in entry["reason"]


def test_an_unresolvable_model_is_unjudged_never_ok(tmp_path, monkeypatch):
    """No session.model / message model → no capacity → UNJUDGED (never a fabricated OK)."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000, model=None)
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "UNJUDGED"
    assert "no resolved model" in reason


def test_missing_catalog_metadata_is_unjudged_never_ok(tmp_path, monkeypatch):
    """A model absent from the installed catalog + config has NO resolvable capacity."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000, model={"providerID": "nope", "id": "ghost"})
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "UNJUDGED"
    assert "no installed metadata" in reason


def test_a_pending_only_session_has_no_usable_measurement(tmp_path, monkeypatch):
    """Reviewer finding, preserved: a pending, zero-valued sample must NOT read as measured."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=1, context=1)
    # Replace the completed sample with the pending shape only.
    con = sqlite3.connect(db)
    con.execute("DELETE FROM message WHERE session_id=?", (sid,))
    con.execute(
        "INSERT INTO message VALUES (?, ?, ?)",
        (sid, 1, json.dumps({"role": "assistant", "tokens": {"total": 0, "input": 0, "output": 0}})),
    )
    con.commit()
    con.close()
    verdict, reason, measured = measure_verdict(sid, db_path=db)
    assert verdict == "UNJUDGED" and measured is True
    assert "no usable measurement" in reason


def test_an_unfinished_usage_row_never_overwrites_a_valid_reading(tmp_path):
    """The zero-overwrite fix: a streaming turn (no tokens) after completed samples keeps the
    last COMPLETED reading and flags the incompleteness — never a silent 0."""
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=7, context=42_000)
    _add_unfinished_assistant_message(db, sid)
    turns, context, incomplete = _measure(db, sid)
    assert turns == 8  # the in-flight turn is still a turn
    assert context == 42_000  # the completed reading survives
    assert incomplete is True


def test_a_pending_zero_valued_message_never_overwrites_a_valid_reading(tmp_path, monkeypatch):
    """Astra's reproduction, verbatim shape: a 240,000 reading followed by a pending
    zero-valued message must still measure 240,000 — and CLOSE against a model whose hard
    limit it exceeds, never 0/OK."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=7, context=240_000, model=SMALL)  # 160K hard limit
    _add_unfinished_assistant_message(db, sid, zero_valued=True)
    turns, context, incomplete = _measure(db, sid)
    assert turns == 8
    assert context == 240_000, "the pending zero-valued message overwrote the reading"
    assert incomplete is True
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "CLOSE", reason


def test_the_runtime_env_supplies_the_identity(tmp_path, monkeypatch):
    """FINOPS_SESSION_ID (the runtime's explicit AIO session identity) is honored."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000)
    monkeypatch.setenv(SESSION_ID_ENV, sid)
    rc = main(["--db", str(db), "--json"])
    assert rc == 0
    journal = (tmp_path / "budget.jsonl").read_text(encoding="utf-8").strip().splitlines()
    entry = json.loads(journal[-1])
    assert entry["session_id"] == sid and entry["verdict"] == "OK"


# ── the report: model, capacity, headroom, effective limit, provenance ──────────


def test_the_report_carries_capacity_headroom_and_provenance(tmp_path, monkeypatch, capsys):
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000)
    rc = main(["--db", str(db), "--session-id", sid, "--json", "--no-journal"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema"] == SCHEMA_ID == "session-budget/v2"
    assert report["model"]["model_id"] == "deepseek-v4-flash" and report["model"]["source"] == "session.model"
    capacity = report["capacity"]
    assert capacity["effective_limit"] == 968_000
    assert capacity["hard_limit"] == 1_000_000
    assert capacity["response_headroom_tokens"] == 32_000
    assert capacity["compaction_reserved_tokens"] == 20_000  # no config → min(20000, 32000)
    assert report["remaining_tokens"] == 968_000 - 30_000
    provenance = report["provenance"]
    assert provenance["formula"] == "opencode@1.18.15:SessionCompaction.isOverflow"
    assert provenance["model_source"] == "session.model"
    assert provenance["catalog_source"] == str(tmp_path / "models.json")
    assert provenance["effective_limit_source"] == "resolved-model-capacity"
    # turns is telemetry in the human render, never a denominator
    human = main(["--db", str(db), "--session-id", sid, "--no-journal"])
    assert human == 0


def test_the_operator_override_is_shared_and_named_in_provenance(tmp_path, monkeypatch):
    """FINOPS_SESSION_CTX_LIMIT is the ONE explicit override — read by the same module the
    CLI, the capsule, and the gate consume, and visible in the provenance."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=120_000)
    assert measure_verdict(sid, db_path=db)[0] == "OK"
    monkeypatch.setenv(sc.EFFECTIVE_LIMIT_ENV, "100000")
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "COMPACT", reason
    capacity, _, _ = sc.resolve_capacity(db, sid)
    assert capacity is not None and capacity.effective_limit == 100_000
    assert capacity.provenance["effective_limit_source"] == sc.EFFECTIVE_LIMIT_ENV


# ── exit codes: COMPACT and CLOSE are distinct ─────────────────────────────────


def test_exit_codes_separate_advisory_compact_and_close(tmp_path, monkeypatch):
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=172_491, model=MID)  # advisory
    assert main(["--db", str(db), "--session-id", sid, "--json", "--no-journal"]) == 1
    _set_model(db, sid, FLASH)
    assert main(["--db", str(db), "--session-id", sid, "--json", "--no-journal"]) == 0
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO message VALUES (?, ?, ?)",
        (sid, 50_000, json.dumps({"role": "assistant", "tokens": {"total": 970_000, "input": 970_000}})),
    )
    con.commit()
    con.close()
    assert main(["--db", str(db), "--session-id", sid, "--json", "--no-journal"]) == 2
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO message VALUES (?, ?, ?)",
        (sid, 60_000, json.dumps({"role": "assistant", "tokens": {"total": 1_000_000, "input": 1_000_000}})),
    )
    con.commit()
    con.close()
    assert main(["--db", str(db), "--session-id", sid, "--json", "--no-journal"]) == 3


def test_main_unreadable_budget_is_unjudged_never_ok(tmp_path, monkeypatch):
    """A missing database is UNJUDGED (exit 1) — an unknown budget is never unlimited."""
    _hermetic(tmp_path, monkeypatch)
    rc = main(["--db", str(tmp_path / "absent.db"), "--session-id", "ses_x", "--json"])
    assert rc == 1


def test_journal_is_append_only(tmp_path, monkeypatch):
    """The journal is append-only: a second judgment is a second line."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000)
    journal = tmp_path / "budget.jsonl"
    main(["--db", str(db), "--session-id", sid, "--no-journal"])
    main(["--db", str(db), "--session-id", sid])
    main(["--db", str(db), "--session-id", sid])
    assert len(journal.read_text(encoding="utf-8").strip().splitlines()) == 2


# ── identity resolution (kept from the prior contract) ──────────────────────────


def test_the_measure_reads_the_open_code_shape(tmp_path: Path):
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=7, context=42_000)
    turns, context, incomplete = _measure(db, sid)
    assert turns == 7
    assert context == 42_000
    assert incomplete is False


def test_a_newer_child_session_never_shadows_the_explicit_identity(tmp_path: Path):
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=7, context=42_000)
    _add_younger_child_session(db, sid)
    assert _resolve_session_id(sid, env={}) == sid
    assert _session_exists(db, sid)
    assert _session_exists(db, "ses_child_newer")
    turns, context, _ = _measure(db, sid)
    assert turns == 7 and context == 42_000  # the CHILD's 1-token row did not leak in


def test_no_identity_supplied_resolves_to_none(tmp_path: Path):
    db = tmp_path / "opencode.db"
    _make_session_db(db, turns=5, context=30_000)
    assert _resolve_session_id(None, env={}) is None
