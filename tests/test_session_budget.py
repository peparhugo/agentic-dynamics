"""Session-budget tests — ``session-budget/v2`` (capacity-derived policy, 2026-09-15).

The operator's context-policy change: the AIO's context management judges against the ACTIVE
session model's resolved capacity (the ported opencode 1.18.15 calculation), NOT a universal
constant; the 80% warning is ADVISORY; message count is TELEMETRY (never a stopping
condition); at the usable boundary the native runtime compacts and the session continues;
CLOSE is reserved for the hard model context limit — or a clamped LOCAL POLICY cap, which is
not a native trigger. The negative half is unchanged: an unreadable budget is UNJUDGED —
never silently OK, exactly as an unknown cost is never zero.

Reviewer-reproduction regressions (2026-09-15) covered here:
* a completed compaction summary followed by a pending assistant turn must not resurrect the
  stale pre-compaction reading (the first resumed submission is allowed);
* the missing-``total`` token sum EXCLUDES ``reasoning`` (955K native, never 975K);
* the config fallback merges files in the runtime's order (project LAST), merges limit fields
  instead of discarding them, and tolerates JSONC trailing commas;
* the runtime CLI resolution is preferred when the binary is available;
* ``FINOPS_SESSION_CTX_LIMIT`` is clamped to the native capacity and is a policy CLOSE — never
  a claimed native compaction;
* a corrupt database yields the structured UNJUDGED, never a crash.

Every test is hermetic: the catalog is a tmp fixture, the runtime CLI is disabled by default
(``FINOPS_SESSION_CAPACITY_SOURCE=catalog``) or pointed at a fake binary, and the runtime
config roots are tmp (``XDG_CONFIG_HOME``).
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


def _hermetic(tmp_path: Path, monkeypatch, *, source: str = "catalog") -> Path:
    """Point the resolver at tmp-only catalog/config roots (no host config can leak in)."""
    cache = _catalog(tmp_path)
    monkeypatch.setenv(sc.MODELS_CACHE_ENV, str(cache))
    monkeypatch.setenv(sc.CAPACITY_SOURCE_ENV, source)
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


def _append_message(path: Path, sid: str, when: int, payload: dict) -> None:
    con = sqlite3.connect(path)
    con.execute("INSERT INTO message VALUES (?, ?, ?)", (sid, when, json.dumps(payload)))
    con.commit()
    con.close()


def _append_compaction_summary(
    path: Path, sid: str, *, summary_tokens: int = 975_000, when: int = 99_000
) -> None:
    """A COMPLETED compaction summary: opencode creates it zero-valued, then the summary
    generation call fills its usage with the OLD conversation's size. It is never a context
    sample; it marks the post-compaction boundary."""
    _append_message(path, sid, when, {
        "role": "assistant", "summary": True, "mode": "compaction",
        "finish": "stop",
        "tokens": {"total": summary_tokens, "input": summary_tokens},
    })


def _append_pending_assistant(path: Path, sid: str, *, when: int = 99_500) -> None:
    _append_message(path, sid, when, {
        "role": "assistant", "tokens": {"total": 0, "input": 0, "output": 0,
                                         "cache": {"read": 0, "write": 0}},
    })


def _add_unfinished_assistant_message(path: Path, sid: str, *, zero_valued: bool = False) -> None:
    """Append a STREAMING assistant message after the completed samples."""
    if zero_valued:
        payload = {"role": "assistant",
                   "tokens": {"total": 0, "input": 0, "output": 0, "reasoning": 0,
                              "cache": {"read": 0, "write": 0}}}
    else:
        payload = {"role": "assistant"}
    _append_message(path, sid, 9000, payload)


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


def _write_opencode_stub(
    path: Path, *, context: int, output: int, model_id: str = "deepseek-v4-flash",
    provider: str = "deepseek", exit_code: int = 0, garbage: bool = False,
) -> Path:
    """A fake ``opencode`` printing the real ``models --verbose`` shape (or failing)."""
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"sys.exit({exit_code}) if {exit_code} else None\n"
        + ("print('not json at all')\n" if garbage else
           f"print('{provider}/{model_id}')\n"
           "print(json.dumps({"
           f"'id': '{model_id}', 'providerID': '{provider}', "
           f"'limit': {{'context': {context}, 'output': {output}}}, "
           "'capabilities': {'reasoning': True}}, indent=2))\n"),
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _project_config(directory: Path, payload: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "opencode.json").write_text(json.dumps(payload), encoding="utf-8")


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


def test_the_measure_is_the_runtimes_overflow_measure_exactly():
    """``total`` first, else ``input + output + cache.read + cache.write`` — reasoning is NOT
    in the sum (reviewer reproduction: 955K native vs 975K when reasoning was added)."""
    assert sc.usage_context_tokens({"total": 123}) == 123
    assert sc.usage_context_tokens({"input": 1, "output": 2, "cache": {"read": 3, "write": 4}}) == 10
    # The reviewer's exact shape: input 900K, cache read 55K, reasoning 20K → 955K, not 975K.
    assert sc.usage_context_tokens(
        {"input": 900_000, "output": 0, "reasoning": 20_000, "cache": {"read": 55_000, "write": 0}}
    ) == 955_000
    assert sc.usage_context_tokens({"total": 0, "input": 0, "cache": {"read": 0}}) is None
    assert sc.usage_context_tokens({}) is None


def test_reasoning_only_is_not_a_measurement():
    assert sc.usage_context_tokens({"reasoning": 500}) is None


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


def test_a_completed_compaction_allows_the_first_resumed_submission(tmp_path, monkeypatch):
    """Reviewer reproduction: a successful compaction followed by a pending assistant turn
    must NOT report the stale 975K / COMPACT. The runtime skips its overflow check for the
    summary; so does the check — the first resumed work is allowed."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=60, context=975_000)
    assert measure_verdict(sid, db_path=db)[0] == "COMPACT"  # before compaction

    _append_compaction_summary(db, sid, summary_tokens=975_000)
    turns, context, incomplete, post_compaction = _measure(db, sid)
    assert turns == 61 and post_compaction is True
    assert incomplete is False  # the summary is not a pending sample

    # The resumed turn is in flight (pending assistant) — the reviewer's exact shape.
    _append_pending_assistant(db, sid)
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "OK", reason
    assert "post-compaction" in reason
    assert _session_exists(db, sid)  # the same session identity — continuity preserved


def test_the_next_completed_sample_clears_the_post_compaction_state(tmp_path, monkeypatch):
    """After the resumed turn completes, the fresh (small) sample is the context again."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=60, context=975_000)
    _append_compaction_summary(db, sid, summary_tokens=975_000)
    _append_pending_assistant(db, sid)  # the resumed turn, in flight
    assert measure_verdict(sid, db_path=db)[0] == "OK"

    _append_message(db, sid, 100_000, {
        "role": "assistant", "tokens": {"total": 30_000, "input": 30_000},
    })
    turns, context, incomplete, post_compaction = _measure(db, sid)
    assert post_compaction is False and context == 30_000 and incomplete is True
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "OK", reason


def test_a_pending_compaction_summary_is_not_post_compaction(tmp_path, monkeypatch):
    """The summary is created zero-valued while compaction is IN FLIGHT: the pre-compaction
    reading stands (the boundary has not moved yet)."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=60, context=975_000)
    _append_message(db, sid, 99_000, {
        "role": "assistant", "summary": True, "mode": "compaction",
        "tokens": {"total": 0, "input": 0, "output": 0, "cache": {"read": 0, "write": 0}},
    })
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "COMPACT", reason


# ── the runtime CLI is the preferred source (authority) ─────────────────────────


def test_the_runtime_cli_resolution_is_preferred(tmp_path, monkeypatch):
    """When the installed binary is available, ITS resolved limits are the source (777K here,
    not the catalog's 1M)."""
    _hermetic(tmp_path, monkeypatch, source="auto")
    binary = _write_opencode_stub(tmp_path / "opencode", context=777_000, output=10_000)
    monkeypatch.setenv(sc.RUNTIME_BIN_ENV, str(binary))
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000)
    capacity, reason, _ = sc.resolve_capacity(db, sid)
    assert capacity is not None, reason
    assert capacity.context_limit == 777_000
    assert capacity.native_effective_limit == 767_000  # 777K - 10K headroom
    assert capacity.provenance["limits_source"].startswith("opencode-cli:")


def test_a_failing_runtime_cli_falls_back_to_the_catalog(tmp_path, monkeypatch):
    _hermetic(tmp_path, monkeypatch, source="auto")
    binary = _write_opencode_stub(tmp_path / "opencode", context=1, output=1, exit_code=3)
    monkeypatch.setenv(sc.RUNTIME_BIN_ENV, str(binary))
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000)
    capacity, reason, _ = sc.resolve_capacity(db, sid)
    assert capacity is not None, reason
    assert capacity.context_limit == 1_000_000  # the fixture catalog
    assert capacity.provenance["limits_source"] == "catalog+config"


def test_a_garbage_runtime_cli_falls_back_to_the_catalog(tmp_path, monkeypatch):
    _hermetic(tmp_path, monkeypatch, source="auto")
    binary = _write_opencode_stub(tmp_path / "opencode", context=1, output=1, garbage=True)
    monkeypatch.setenv(sc.RUNTIME_BIN_ENV, str(binary))
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000)
    capacity, _, _ = sc.resolve_capacity(db, sid)
    assert capacity is not None and capacity.context_limit == 1_000_000


# ── the config fallback matches the runtime's loading/merging ───────────────────


def test_project_settings_win_over_the_explicit_config(tmp_path, monkeypatch):
    """opencode merges global → OPENCODE_CONFIG → project (project LAST); the fallback must
    too (reviewer finding: the order was backwards)."""
    _hermetic(tmp_path, monkeypatch)
    config_home = tmp_path / "config-home" / "opencode"
    config_home.mkdir(parents=True, exist_ok=True)
    (config_home / "opencode.json").write_text(json.dumps({
        "provider": {"deepseek": {"models": {"deepseek-v4-flash": {"limit": {"context": 900_000}}}}}
    }), encoding="utf-8")
    explicit = tmp_path / "explicit.json"
    explicit.write_text(json.dumps({
        "provider": {"deepseek": {"models": {"deepseek-v4-flash": {"limit": {"context": 800_000}}}}}
    }), encoding="utf-8")
    monkeypatch.setenv(sc.OPENCODE_CONFIG_ENV, str(explicit))
    project = tmp_path / "project"
    _project_config(project, {
        "provider": {"deepseek": {"models": {"deepseek-v4-flash": {"limit": {"context": 700_000}}}}}
    })
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000, directory=str(project))
    capacity, reason, _ = sc.resolve_capacity(db, sid)
    assert capacity is not None, reason
    assert capacity.context_limit == 700_000  # the project file wins, applied last


def test_a_partial_override_keeps_the_inherited_fields(tmp_path, monkeypatch):
    """A project override of only ``output`` must NOT discard the inherited ``context``."""
    _hermetic(tmp_path, monkeypatch)
    config_home = tmp_path / "config-home" / "opencode"
    config_home.mkdir(parents=True, exist_ok=True)
    (config_home / "opencode.json").write_text(json.dumps({
        "provider": {"deepseek": {"models": {"deepseek-v4-flash": {"limit": {"context": 900_000}}}}}
    }), encoding="utf-8")
    project = tmp_path / "project"
    _project_config(project, {
        "provider": {"deepseek": {"models": {"deepseek-v4-flash": {"limit": {"output": 12_000}}}}}
    })
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000, directory=str(project))
    capacity, reason, _ = sc.resolve_capacity(db, sid)
    assert capacity is not None, reason
    assert capacity.context_limit == 900_000  # inherited from the global file
    assert capacity.response_headroom_tokens == 12_000  # overridden by the project file


def test_jsonc_trailing_commas_are_tolerated(tmp_path, monkeypatch):
    """The runtime's JSONC parser accepts trailing commas; the fallback must not discard a
    valid config because of them (reviewer finding)."""
    _hermetic(tmp_path, monkeypatch)
    project = tmp_path / "project"
    project.mkdir(parents=True, exist_ok=True)
    (project / "opencode.jsonc").write_text(
        "{\n"
        "  // the runtime's own JSONC dialect\n"
        "  \"provider\": {\n"
        "    \"deepseek\": {\n"
        "      \"models\": {\n"
        "        \"deepseek-v4-flash\": {\n"
        "          \"limit\": {\n"
        "            \"context\": 640000,\n"
        "          },\n"
        "        },\n"
        "      },\n"
        "    },\n"
        "  },\n"
        "}\n",
        encoding="utf-8",
    )
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000, directory=str(project))
    capacity, reason, _ = sc.resolve_capacity(db, sid)
    assert capacity is not None, reason
    assert capacity.context_limit == 640_000


def test_project_config_can_be_disabled(tmp_path, monkeypatch):
    _hermetic(tmp_path, monkeypatch)
    project = tmp_path / "project"
    _project_config(project, {
        "provider": {"deepseek": {"models": {"deepseek-v4-flash": {"limit": {"context": 500_000}}}}}
    })
    monkeypatch.setenv("OPENCODE_DISABLE_PROJECT_CONFIG", "1")
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000, directory=str(project))
    capacity, reason, _ = sc.resolve_capacity(db, sid)
    assert capacity is not None, reason
    assert capacity.context_limit == 1_000_000  # the fixture catalog, project ignored


# ── the policy override: clamped, and never a native compaction claim ───────────


def test_the_policy_override_is_clamped_to_native_capacity(tmp_path, monkeypatch):
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000)
    monkeypatch.setenv(sc.EFFECTIVE_LIMIT_ENV, "5000000")  # far above native
    capacity, _, _ = sc.resolve_capacity(db, sid)
    assert capacity is not None
    assert capacity.native_effective_limit == 968_000
    assert capacity.policy_limit == 968_000  # clamped, never above native
    assert capacity.effective_limit == 968_000
    assert capacity.provenance["effective_limit_source"] == "FINOPS_SESSION_CTX_LIMIT(policy)"


def test_crossing_a_policy_limit_is_a_policy_close_not_a_compaction(tmp_path, monkeypatch):
    """Reviewer finding: with FINOPS_SESSION_CTX_LIMIT=100K, 120K usage must NOT claim
    'COMPACT' (returning COMPACT does not initiate compaction) — it is a LOCAL POLICY close."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=120_000)
    assert measure_verdict(sid, db_path=db)[0] == "OK"
    monkeypatch.setenv(sc.EFFECTIVE_LIMIT_ENV, "100000")
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "CLOSE", reason
    assert "LOCAL POLICY" in reason and "not a native trigger" in reason

    # Above the native boundary the NATIVE verdict still governs (COMPACT), even with a
    # low policy cap — the native runtime is the active mechanism there.
    _append_message(db, sid, 50_000, {
        "role": "assistant", "tokens": {"total": 970_000, "input": 970_000},
    })
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "COMPACT", reason
    assert "native compaction boundary" in reason


# ── honest unavailable states ───────────────────────────────────────────────────


def test_missing_identity_is_a_refusal_not_a_guess(tmp_path, monkeypatch):
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
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    _make_session_db(db, turns=5, context=30_000)
    rc = main(["--db", str(db), "--session-id", "ses_nonexistent", "--json"])
    assert rc == 1
    journal = (tmp_path / "budget.jsonl").read_text(encoding="utf-8").strip().splitlines()
    entry = json.loads(journal[-1])
    assert entry["verdict"] == "UNJUDGED"
    assert "does not exist" in entry["reason"]


def test_a_corrupt_database_is_unjudged_and_the_cli_still_emits_json(tmp_path, monkeypatch, capsys):
    """Reviewer finding: the session lookup must sit inside the shared error boundary — a
    corrupt database yields the structured UNJUDGED, never a crashed CLI."""
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "corrupt.db"
    db.write_bytes(b"this is not a sqlite database" * 100)
    rc = main(["--db", str(db), "--session-id", "ses_x", "--json", "--no-journal"])
    assert rc == 1
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == "UNJUDGED"
    assert report["reason"]  # named, never silent
    assert measure_verdict("ses_x", db_path=db)[0] == "UNJUDGED"


def test_an_unresolvable_model_is_unjudged_never_ok(tmp_path, monkeypatch):
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000, model=None)
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "UNJUDGED"
    assert "no resolved model" in reason


def test_missing_catalog_metadata_is_unjudged_never_ok(tmp_path, monkeypatch):
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000, model={"providerID": "nope", "id": "ghost"})
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "UNJUDGED"
    assert "no installed metadata" in reason


def test_a_pending_only_session_has_no_usable_measurement(tmp_path, monkeypatch):
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=1, context=1)
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
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=7, context=42_000)
    _add_unfinished_assistant_message(db, sid)
    turns, context, incomplete, _ = _measure(db, sid)
    assert turns == 8  # the in-flight turn is still a turn
    assert context == 42_000  # the completed reading survives
    assert incomplete is True


def test_a_pending_zero_valued_message_never_overwrites_a_valid_reading(tmp_path, monkeypatch):
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=7, context=240_000, model=SMALL)  # 160K hard limit
    _add_unfinished_assistant_message(db, sid, zero_valued=True)
    turns, context, incomplete, _ = _measure(db, sid)
    assert turns == 8
    assert context == 240_000, "the pending zero-valued message overwrote the reading"
    assert incomplete is True
    verdict, reason, _ = measure_verdict(sid, db_path=db)
    assert verdict == "CLOSE", reason


def test_the_runtime_env_supplies_the_identity(tmp_path, monkeypatch):
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
    assert capacity["native_effective_limit"] == 968_000
    assert capacity["policy_limit"] is None
    assert capacity["hard_limit"] == 1_000_000
    assert capacity["response_headroom_tokens"] == 32_000
    assert capacity["compaction_reserved_tokens"] == 20_000  # no config → min(20000, 32000)
    assert report["remaining_tokens"] == 968_000 - 30_000
    provenance = report["provenance"]
    assert provenance["formula"] == "opencode@1.18.15:SessionCompaction.isOverflow"
    assert provenance["model_source"] == "session.model"
    assert provenance["limits_source"] == "catalog+config"
    assert provenance["effective_limit_source"] == "resolved-model-capacity"
    assert human_rc(["--db", str(db), "--session-id", sid, "--no-journal"]) == 0


def human_rc(argv: list[str]) -> int:
    """The human-render path exit code (journal already covered above)."""
    import contextlib as _ctx
    import io as _io

    with _ctx.redirect_stdout(_io.StringIO()):
        return main(argv)


# ── exit codes: COMPACT and CLOSE are distinct ─────────────────────────────────


def test_exit_codes_separate_advisory_compact_and_close(tmp_path, monkeypatch):
    _hermetic(tmp_path, monkeypatch)
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=172_491, model=MID)  # advisory
    assert main(["--db", str(db), "--session-id", sid, "--json", "--no-journal"]) == 1
    _set_model(db, sid, FLASH)
    assert main(["--db", str(db), "--session-id", sid, "--json", "--no-journal"]) == 0
    _append_message(db, sid, 50_000, {
        "role": "assistant", "tokens": {"total": 970_000, "input": 970_000},
    })
    assert main(["--db", str(db), "--session-id", sid, "--json", "--no-journal"]) == 2
    _append_message(db, sid, 60_000, {
        "role": "assistant", "tokens": {"total": 1_000_000, "input": 1_000_000},
    })
    assert main(["--db", str(db), "--session-id", sid, "--json", "--no-journal"]) == 3


def test_main_unreadable_budget_is_unjudged_never_ok(tmp_path, monkeypatch):
    _hermetic(tmp_path, monkeypatch)
    rc = main(["--db", str(tmp_path / "absent.db"), "--session-id", "ses_x", "--json"])
    assert rc == 1


def test_journal_is_append_only(tmp_path, monkeypatch):
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
    turns, context, incomplete, post_compaction = _measure(db, sid)
    assert turns == 7
    assert context == 42_000
    assert incomplete is False
    assert post_compaction is False


def test_a_newer_child_session_never_shadows_the_explicit_identity(tmp_path: Path):
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=7, context=42_000)
    _add_younger_child_session(db, sid)
    assert _resolve_session_id(sid, env={}) == sid
    assert _session_exists(db, sid)
    assert _session_exists(db, "ses_child_newer")
    turns, context, _, _ = _measure(db, sid)
    assert turns == 7 and context == 42_000  # the CHILD's 1-token row did not leak in


def test_no_identity_supplied_resolves_to_none(tmp_path: Path):
    db = tmp_path / "opencode.db"
    _make_session_db(db, turns=5, context=30_000)
    assert _resolve_session_id(None, env={}) is None
