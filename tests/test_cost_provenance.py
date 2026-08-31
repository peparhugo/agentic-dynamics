"""Cost provenance + settlement — phase 3 of the ``admission_leases`` work order.

The property under test, stated once: **a cost figure carries where it came from, and a
missing cost is never the number zero.**

The suite is organised as the work order's VERIFY clause is, in both directions:

1. ``TestFiveStateCollapseIsUndone`` — a provider-reported zero is distinguishable from a
   missing cost, at the resolver, at both adapters, and after a full parse.
2. ``TestZeroCoercionIsGone`` — the specific removed defect (``total_cost_usd`` → ``0.0``),
   asserted against the source and against behaviour.
3. ``TestLedgerCarriesProvenance`` — ``cost_source`` survives a full run, from the adapter
   through ``SessionResult``/``PhaseResult`` to the ledger dict.
4. ``TestUnknownCostDenial`` — an unpriced per-token invocation is refused AT THE ADAPTER, and
   the refusal means no invocation happened.
5. ``TestSettlement`` — the reservation is reconciled against the provider's meter, and an
   absent meter reading settles as UNSETTLED rather than as $0.

Everything here is deterministic: no model is invoked, no network call is made, and every
clock/ledger is injected.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentic_dynamics.adapters.claude_adapter import ClaudeStreamAdapter, adapt_usage
from agentic_dynamics.adapters.opencode import AgenticResult, _parse_session_output
from agentic_dynamics.control.settlement import (
    Settlement,
    SettlementStatus,
    classify_variance,
    load_usage_ledger,
    platform_day_cost_usd,
    record_settlement,
    settle,
    window_used_percent,
)
from agentic_dynamics.core.admission_context import (
    ADMISSION_ENV_KEYS,
    ADMISSION_REQUIRED_ENV,
    COST_SOURCE_ENV,
    AdmissionContextError,
    LeaseContext,
    bind_context,
)
from agentic_dynamics.core.cost_provenance import (
    METHOD_PLATFORM_METER_DAILY,
    METHOD_TOKEN_PRICE_TABLE,
    CostObservation,
    CostSource,
    ProviderClass,
    coerce_cost_source,
    is_per_token_model,
    provider_class_or_none,
    resolve_cost_observation,
)
from agentic_dynamics.experiment.experiment_spec import LEDGER_FIELDS
from agentic_dynamics.runtime.story.models import SessionResult
from agentic_dynamics.runtime.workflow_runner import PhaseResult

ROOT = Path(__file__).resolve().parent.parent

PER_TOKEN_MODEL = "deepseek/deepseek-v4-flash"
SUBSCRIPTION_MODEL = "anthropic/claude-haiku-4-5"

USAGE = {"input_tokens": 100, "output_tokens": 50}


@pytest.fixture
def armed(monkeypatch):
    """Arm the admission gate and clear any inherited admission env block."""
    monkeypatch.setenv(ADMISSION_REQUIRED_ENV, "1")
    for key in ADMISSION_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _claude_events(event: dict) -> list[dict]:
    """Feed one Claude ``result`` event through the stream adapter."""
    adapter = ClaudeStreamAdapter()
    adapter.feed({"type": "system"})
    return adapter.feed(event)


def _parse(events: list[dict]) -> AgenticResult:
    """Parse translated opencode events into a fresh result."""
    result = AgenticResult()
    _parse_session_output("\n".join(json.dumps(e) for e in events), result)
    return result


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 1. The five-state collapse is undone
# ═══════════════════════════════════════════════════════════════════════════════════════════


class TestFiveStateCollapseIsUndone:
    """Five situations that all used to arrive as ``0.0`` are now five distinct states."""

    def test_metered_zero_is_a_measurement(self):
        # A provider that reports $0 for a session that spent no tokens metered a real zero.
        obs = resolve_cost_observation(reported_cost_usd=0.0, tokens_observed=False)
        assert obs.source is CostSource.METERED
        assert obs.cost_usd == 0.0
        assert obs.reported_cost_usd == 0.0
        assert obs.is_trusted

    def test_missing_cost_is_none_not_zero(self):
        # THE bug. No figure reported and nothing estimable ⇒ UNKNOWN with cost_usd=None.
        obs = resolve_cost_observation(reported_cost_usd=None, tokens_observed=False)
        assert obs.source is CostSource.UNKNOWN
        assert obs.cost_usd is None, "a missing cost must never be the number zero"
        assert obs.reported_cost_usd is None
        assert not obs.is_trusted

    def test_metered_zero_and_missing_cost_are_distinguishable(self):
        """The headline property, stated as a direct comparison of the two observations."""
        metered = resolve_cost_observation(reported_cost_usd=0.0, tokens_observed=False)
        missing = resolve_cost_observation(reported_cost_usd=None, tokens_observed=False)
        assert metered != missing
        assert (metered.source, metered.reported_cost_usd) == (CostSource.METERED, 0.0)
        assert (missing.source, missing.reported_cost_usd) == (CostSource.UNKNOWN, None)
        # Both project a 0.0 *billable* figure — which is exactly why the source field has to
        # exist: the float alone cannot carry the difference.
        assert metered.billable_usd == missing.billable_usd == 0.0

    def test_placeholder_zero_with_tokens_defers_to_the_estimate(self):
        # opencode emits ``cost: 0`` for providers it does not price. Tokens were spent, so the
        # zero is a placeholder — but it is still RECORDED as a reported zero.
        obs = resolve_cost_observation(
            reported_cost_usd=0.0, estimated_cost_usd=0.42, tokens_observed=True
        )
        assert obs.source is CostSource.ESTIMATED
        assert obs.cost_usd == 0.42
        assert obs.reported_cost_usd == 0.0, "the observed zero must survive as evidence"
        assert obs.estimation_method == METHOD_TOKEN_PRICE_TABLE

    def test_positive_meter_reading_wins_over_any_estimate(self):
        obs = resolve_cost_observation(
            reported_cost_usd=1.25, estimated_cost_usd=99.0, tokens_observed=True
        )
        assert (obs.source, obs.cost_usd) == (CostSource.METERED, 1.25)
        assert obs.estimation_method is None

    def test_unpriceable_run_with_tokens_is_unknown_not_free(self):
        # Tokens were spent but no price table covered the model: UNKNOWN, not $0.00.
        obs = resolve_cost_observation(
            reported_cost_usd=None, estimated_cost_usd=None, tokens_observed=True
        )
        assert obs.source is CostSource.UNKNOWN
        assert obs.cost_usd is None

    def test_bool_is_not_a_cost(self):
        # ``True`` is an ``int`` in Python; without the bool guard it would become $1.00.
        obs = resolve_cost_observation(reported_cost_usd=True, tokens_observed=False)
        assert obs.source is CostSource.UNKNOWN

    @pytest.mark.parametrize("bad", ["", "  ", "free", "METERED_ISH", None, 3])
    def test_coerce_cost_source_never_guesses(self, bad):
        assert coerce_cost_source(bad) is None

    def test_coerce_cost_source_round_trips_every_member(self):
        for member in CostSource:
            assert coerce_cost_source(member.value) is member
            assert coerce_cost_source(member) is member


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 2. The zero-coercion is gone (the specific defect the work order names)
# ═══════════════════════════════════════════════════════════════════════════════════════════


class TestZeroCoercionIsGone:
    """``adapt_usage``'s ``total_cost_usd`` → ``0.0`` coercion, asserted dead."""

    def test_absent_total_cost_usd_stays_none(self):
        assert adapt_usage(USAGE, None)["cost"] is None

    def test_reported_zero_stays_zero(self):
        assert adapt_usage(USAGE, 0.0)["cost"] == 0.0

    def test_reported_positive_passes_through(self):
        assert adapt_usage(USAGE, 0.01)["cost"] == 0.01

    def test_default_argument_is_not_zero(self):
        """The default itself was half the bug — ``adapt_usage(usage)`` must not mean $0."""
        assert adapt_usage(USAGE)["cost"] is None

    def test_stream_adapter_omits_the_cost_key_when_claude_reports_none(self):
        # A subscription run reports no ``total_cost_usd``; the translated event must not
        # invent one. Absence is how the opencode schema expresses "no cost reported".
        events = _claude_events({"type": "result", "usage": USAGE})
        finish = [e for e in events if e["type"] == "step_finish"][0]
        assert "cost" not in finish["part"]

    def test_stream_adapter_preserves_a_reported_zero(self):
        events = _claude_events({"type": "result", "usage": USAGE, "total_cost_usd": 0.0})
        finish = [e for e in events if e["type"] == "step_finish"][0]
        assert finish["part"]["cost"] == 0.0

    def test_the_coercion_is_absent_from_the_source(self):
        """A source-level guard so the coercion cannot be reintroduced by a later edit.

        Compares EXECUTABLE code only: the module is parsed and unparsed through ``ast``,
        which drops comments and (once docstrings are stripped) prose. Without that, this
        test would fire on any docstring — including the one in ``adapt_usage`` that
        documents the very coercion it removed.
        """
        import ast

        src = (ROOT / "src" / "agentic_dynamics" / "adapters" / "claude_adapter.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(
                node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ) and ast.get_docstring(node) is not None:
                node.body = node.body[1:]  # drop the docstring statement
        code = ast.unparse(tree)

        assert "total_cost_usd', 0.0" not in code and 'total_cost_usd", 0.0' not in code
        assert "total_cost_usd or 0.0" not in code
        # And the positive statement of the replacement, so the guard cannot pass vacuously
        # (e.g. if the function were deleted outright).
        assert "def adapt_usage" in code


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 3. Provenance survives a full run, all the way to the ledger
# ═══════════════════════════════════════════════════════════════════════════════════════════


class TestLedgerCarriesProvenance:
    """From the transcript, through the adapters, onto the ledger records."""

    def test_parser_records_a_reported_zero_distinctly_from_no_cost_key(self):
        zero = _parse([{"type": "step_finish",
                        "part": {"tokens": {"input": 10, "output": 5}, "cost": 0}}])
        absent = _parse([{"type": "step_finish",
                          "part": {"tokens": {"input": 10, "output": 5}}}])
        assert zero.reported_cost_usd == 0.0
        assert absent.reported_cost_usd is None

    def test_parser_marks_a_positive_step_cost_metered(self):
        result = _parse([{"type": "step_finish",
                          "part": {"tokens": {"input": 10, "output": 5}, "cost": 0.02}}])
        assert result.cost_source is CostSource.METERED
        assert result.estimated_cost_usd == 0.02
        assert result.reported_cost_usd == 0.02

    def test_cumulative_cost_detection_still_takes_the_last_value(self):
        """The pre-existing cumulative-vs-delta arithmetic must be numerically unchanged."""
        result = _parse([
            {"type": "step_finish", "part": {"tokens": {"input": 1}, "cost": 0.01}},
            {"type": "step_finish", "part": {"tokens": {"input": 1}, "cost": 0.03}},
        ])
        assert result.estimated_cost_usd == 0.03  # cumulative → last, not the 0.04 sum

    def test_per_step_delta_costs_still_sum(self):
        result = _parse([
            {"type": "step_finish", "part": {"tokens": {"input": 1}, "cost": 0.03}},
            {"type": "step_finish", "part": {"tokens": {"input": 1}, "cost": 0.01}},
        ])
        assert result.estimated_cost_usd == pytest.approx(0.04)  # decreasing → per-step sum

    def test_agentic_result_defaults_to_unknown_not_metered_zero(self):
        """A freshly built result has measured nothing and must not claim otherwise."""
        result = AgenticResult()
        assert result.cost_source is CostSource.UNKNOWN
        assert result.reported_cost_usd is None
        assert not result.cost_is_trusted
        assert result.cost_observation.cost_usd is None

    def test_apply_cost_observation_keeps_the_four_fields_consistent(self):
        result = AgenticResult()
        result.apply_cost_observation(
            CostObservation(
                cost_usd=0.5, source=CostSource.ESTIMATED,
                estimation_method=METHOD_TOKEN_PRICE_TABLE, reported_cost_usd=0.0,
            )
        )
        assert result.estimated_cost_usd == 0.5
        assert result.cost_source is CostSource.ESTIMATED
        assert result.estimation_method == METHOD_TOKEN_PRICE_TABLE
        assert result.reported_cost_usd == 0.0
        # Round-trips back out through the property unchanged.
        assert result.cost_observation.cost_usd == 0.5

    def test_normalized_event_marks_whether_a_cost_was_reported(self):
        """The post-hoc trajectory surface keeps its float, but records the distinction.

        ``scripts/analyze_trajectories.py`` sums ``cost`` unconditionally, so that field must
        stay a float — the additive ``cost_reported`` bit is what says whether the 0.0 is a
        measurement or a placeholder.
        """
        from agentic_dynamics.adapters.opencode import normalize_opencode_event

        reported = normalize_opencode_event(
            {"type": "step_finish", "part": {"tokens": {}, "cost": 0.0}}
        )
        absent = normalize_opencode_event({"type": "step_finish", "part": {"tokens": {}}})
        assert reported["cost"] == absent["cost"] == 0.0  # arithmetic unchanged
        assert reported["cost_reported"] is True
        assert absent["cost_reported"] is False

    def test_run_py_records_cost_provenance(self):
        """The experiment single-task/perturbed records carry provenance (cf. run.py)."""
        src = (ROOT / "scripts" / "run.py").read_text()
        assert src.count('"cost_source": r.cost_source.value') == 2
        assert src.count('"reported_cost_usd": r.reported_cost_usd') == 2

    def test_ledger_fields_declare_the_provenance_columns(self):
        for field in (
            "cost_source", "estimation_method", "reported_cost_usd",
            "settled_cost_usd", "settlement_status",
        ):
            assert field in LEDGER_FIELDS, f"{field} is not a declared ledger field"

    def test_session_result_dict_carries_provenance(self):
        """The story ledger: an attempt's cost provenance reaches the on-disk record."""
        agentic = AgenticResult()
        agentic.apply_cost_observation(
            CostObservation(
                cost_usd=0.25, source=CostSource.ESTIMATED,
                estimation_method=METHOD_TOKEN_PRICE_TABLE, reported_cost_usd=0.0,
            )
        )
        record = SessionResult(
            session_number=1, task_type="x", prompt="p", agentic=agentic,
            cost_usd=0.25, cost_source=agentic.cost_source.value,
            estimation_method=agentic.estimation_method,
            reported_cost_usd=agentic.reported_cost_usd,
        ).to_dict()

        assert record["cost_source"] == "estimated"
        assert record["estimation_method"] == METHOD_TOKEN_PRICE_TABLE
        assert record["reported_cost_usd"] == 0.0
        # And on the nested agentic block, so either read-level is self-describing.
        assert record["agentic"]["cost_source"] == "estimated"
        assert record["agentic"]["reported_cost_usd"] == 0.0

    def test_session_result_defaults_are_unknown(self):
        record = SessionResult(session_number=1, task_type="x", prompt="p").to_dict()
        assert record["cost_source"] == CostSource.UNKNOWN.value
        assert record["reported_cost_usd"] is None

    def test_phase_result_dict_carries_provenance(self):
        """The workflow-run ledger: same property, other record type."""
        record = PhaseResult(
            phase="build", kind="agent", status="ok", cost_usd=1.5,
            cost_source=CostSource.METERED.value, reported_cost_usd=1.5,
        ).to_dict()
        assert record["cost_source"] == "metered"
        assert record["reported_cost_usd"] == 1.5
        assert record["estimation_method"] is None

    def test_phase_result_defaults_are_unknown(self):
        record = PhaseResult(phase="build", kind="agent", status="ok").to_dict()
        assert record["cost_source"] == CostSource.UNKNOWN.value
        assert record["reported_cost_usd"] is None

    def test_provenance_survives_a_full_run_end_to_end(self, monkeypatch, tmp_path):
        """The work order's clause verbatim: cost_source survives a FULL run.

        Drives ``run_opencode_agentic`` with a stubbed subprocess so a real transcript is
        parsed, a real cost decision is made, and the result reaches a ledger record — with
        zero paid invocations.
        """
        from agentic_dynamics.adapters import opencode

        transcript = "\n".join(json.dumps(e) for e in [
            {"type": "step_start", "part": {"type": "step-start"}},
            {"type": "tool_use", "part": {"type": "tool", "tool": "write",
                                          "state": {"status": "completed", "input": {}, "output": ""}}},
            # A metered per-step cost — the provider's own figure.
            {"type": "step_finish", "part": {"tokens": {"input": 100, "output": 50}, "cost": 0.02}},
        ])

        class _Stream:
            stdout = transcript
            stderr = ""
            exit_code = 0
            timed_out = False

        monkeypatch.setattr(opencode, "stream_subprocess", lambda *a, **k: _Stream())
        monkeypatch.setattr(opencode, "_init_git_workdir", lambda *a, **k: None)

        result = opencode.run_opencode_agentic(
            "task", model=PER_TOKEN_MODEL, workdir=str(tmp_path), init_git=False,
        )

        assert result.cost_source is CostSource.METERED
        assert result.estimated_cost_usd == 0.02
        assert result.reported_cost_usd == 0.02

        ledger_row = SessionResult(
            session_number=1, task_type="x", prompt="p", agentic=result,
            cost_source=result.cost_source.value,
            reported_cost_usd=result.reported_cost_usd,
        ).to_dict()
        assert ledger_row["cost_source"] == "metered"
        assert ledger_row["agentic"]["cost_source"] == "metered"

    def test_a_run_with_no_usage_at_all_ends_unknown(self, monkeypatch, tmp_path):
        """The counter-direction: an empty transcript must NOT produce a $0.00 metered run."""
        from agentic_dynamics.adapters import opencode

        class _Stream:
            stdout = ""
            stderr = ""
            exit_code = 0
            timed_out = False

        monkeypatch.setattr(opencode, "stream_subprocess", lambda *a, **k: _Stream())
        monkeypatch.setattr(opencode, "_init_git_workdir", lambda *a, **k: None)

        result = opencode.run_opencode_agentic(
            "task", model=PER_TOKEN_MODEL, workdir=str(tmp_path), init_git=False,
        )
        assert result.cost_source is CostSource.UNKNOWN
        assert result.reported_cost_usd is None
        assert not result.cost_is_trusted


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 4. Unknown cost is never free — denial at the adapter
# ═══════════════════════════════════════════════════════════════════════════════════════════


class TestUnknownCostDenial:
    """The work order's "unknown-cost denial is tested at the adapter level"."""

    def test_provider_class_lookup_is_a_closed_allowlist(self):
        assert provider_class_or_none("deepseek") is ProviderClass.PER_TOKEN
        assert provider_class_or_none("anthropic") is ProviderClass.SUBSCRIPTION
        assert provider_class_or_none("acme-llm") is None

    @pytest.mark.parametrize(
        "model,expected",
        [
            ("deepseek/deepseek-v4-pro", True),
            ("anthropic/claude-opus-5", False),
            ("openai/gpt-5.6-sol", False),
            # Fail-closed: unclassified provider and unparseable id both count as per-token.
            ("acme/whatever", True),
            ("", True),
            ("no-slash", True),
        ],
    )
    def test_is_per_token_model_fails_closed(self, model, expected):
        assert is_per_token_model(model) is expected

    def test_run_agentic_refuses_an_unpriced_per_token_admission(self, armed, monkeypatch):
        """The denial, with a poisoned adapter proving NO invocation happened."""
        from agentic_dynamics.adapters import backends, opencode

        monkeypatch.setattr(
            opencode, "run_opencode_agentic",
            lambda *a, **k: pytest.fail("an unpriced per-token run must never reach the backend"),
        )
        context = LeaseContext(
            run_id="r", model=PER_TOKEN_MODEL, budget_lease_id="b", expires_at=9e9,
            cost_source=CostSource.UNKNOWN,
        )
        with bind_context(context), pytest.raises(
            AdmissionContextError, match="unknown cost is never free"
        ):
            backends.run_agentic("do the thing", model=PER_TOKEN_MODEL)

    def test_run_agentic_refuses_when_provenance_is_unstated(self, armed, monkeypatch):
        """An older/hand-built envelope with no provenance at all is refused too."""
        from agentic_dynamics.adapters import backends, opencode

        monkeypatch.setattr(
            opencode, "run_opencode_agentic",
            lambda *a, **k: pytest.fail("an unpriced per-token run must never reach the backend"),
        )
        context = LeaseContext(
            run_id="r", model=PER_TOKEN_MODEL, budget_lease_id="b", expires_at=9e9,
        )
        with bind_context(context), pytest.raises(
            AdmissionContextError, match="cost_source=unstated"
        ):
            backends.run_agentic("do the thing", model=PER_TOKEN_MODEL)

    @pytest.mark.parametrize(
        "source", [CostSource.METERED, CostSource.ESTIMATED, CostSource.RECONCILED]
    )
    def test_a_priced_per_token_admission_proceeds(self, armed, monkeypatch, source):
        """The other direction: every TRUSTED provenance is admitted."""
        from agentic_dynamics.adapters import backends, opencode

        calls: list[str] = []
        monkeypatch.setattr(
            opencode, "run_opencode_agentic",
            lambda prompt, **kwargs: calls.append(prompt) or AgenticResult(),
        )
        context = LeaseContext(
            run_id="r", model=PER_TOKEN_MODEL, budget_lease_id="b", expires_at=9e9,
            cost_source=source,
        )
        with bind_context(context):
            backends.run_agentic("do the thing", model=PER_TOKEN_MODEL)
        assert calls == ["do the thing"]

    def test_a_subscription_run_needs_no_priced_reservation(self, armed, monkeypatch):
        """Scoping check: the rule must not deny every Claude phase for no safety gain."""
        from agentic_dynamics.adapters import backends, claude_adapter

        calls: list[str] = []
        monkeypatch.setattr(
            claude_adapter, "run_claude_agentic",
            lambda prompt, **kwargs: calls.append(prompt) or AgenticResult(),
        )
        context = LeaseContext(
            run_id="r", model=SUBSCRIPTION_MODEL, budget_lease_id="b", expires_at=9e9,
        )
        with bind_context(context):
            backends.run_agentic("do the thing", model=SUBSCRIPTION_MODEL)
        assert calls == ["do the thing"]

    def test_the_disarmed_default_is_unaffected(self, monkeypatch):
        """Hard rule 3 — the freeze stays, and the gate stays OFF until an operator arms it."""
        from agentic_dynamics.adapters import backends, opencode

        monkeypatch.delenv(ADMISSION_REQUIRED_ENV, raising=False)
        calls: list[str] = []
        monkeypatch.setattr(
            opencode, "run_opencode_agentic",
            lambda prompt, **kwargs: calls.append(prompt) or AgenticResult(),
        )
        backends.run_agentic("do the thing", model=PER_TOKEN_MODEL)
        assert calls == ["do the thing"]

    def test_cost_source_round_trips_through_the_env_transport(self):
        """The provenance must survive the cross-process boundary, or the child refuses."""
        context = LeaseContext(
            run_id="r", model=PER_TOKEN_MODEL, budget_lease_id="b", expires_at=9e9,
            cost_source=CostSource.ESTIMATED,
        )
        env = context.to_env()
        assert env[COST_SOURCE_ENV] == "estimated"
        assert LeaseContext.from_env(env).cost_source is CostSource.ESTIMATED

    def test_an_unstated_env_block_reads_back_as_untrusted(self):
        context = LeaseContext(run_id="r", model=PER_TOKEN_MODEL, budget_lease_id="b")
        env = context.to_env()
        assert env[COST_SOURCE_ENV] == ""
        rebuilt = LeaseContext.from_env(env)
        assert rebuilt.cost_source is None
        assert not rebuilt.cost_is_trusted

    def test_a_forged_env_value_degrades_to_untrusted(self):
        """A typo must not become a permission."""
        context = LeaseContext(run_id="r", model=PER_TOKEN_MODEL, budget_lease_id="b")
        env = context.to_env()
        env[COST_SOURCE_ENV] = "definitely-metered"
        assert LeaseContext.from_env(env).cost_is_trusted is False


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 5. Settlement against the meter
# ═══════════════════════════════════════════════════════════════════════════════════════════


NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)

LEDGER = {
    "schema": "subscription-usage/v3",
    "providers": {
        "anthropic": {
            "ok": True,
            "windows": [
                {"name": "five_hour", "used_percent": 1.0},
                {"name": "seven_day", "used_percent": 16.0},
            ],
        },
        "openai": {"ok": False},
    },
    "deepseek_platform": {
        "ok": True,
        "days": [
            {"date": "2026-08-30", "estimated_cost_usd": 20.19},
            {"date": "2026-08-31", "estimated_cost_usd": 6.60},
        ],
    },
}


class TestSettlement:
    """Reconcile the reservation against the provider's own meter."""

    # -- the extractors ---------------------------------------------------------------------

    def test_platform_day_cost_reads_the_day_bucket(self):
        assert platform_day_cost_usd(LEDGER, "2026-08-31") == 6.60

    def test_a_day_the_meter_never_reported_is_none_not_zero(self):
        assert platform_day_cost_usd(LEDGER, "2026-08-01") is None

    def test_an_unhealthy_meter_block_is_none(self):
        assert platform_day_cost_usd({"deepseek_platform": {"ok": False}}, "2026-08-31") is None

    def test_window_usage_takes_the_binding_window(self):
        # The 5h window is at 1% and the 7d at 16%; the binding constraint is the max.
        assert window_used_percent(LEDGER, "anthropic") == 16.0

    def test_window_usage_can_select_one_window(self):
        assert window_used_percent(LEDGER, "anthropic", window="five_hour") == 1.0

    def test_an_unhealthy_provider_block_is_none(self):
        assert window_used_percent(LEDGER, "openai") is None

    # -- the variance band ------------------------------------------------------------------

    def test_variance_band_has_an_absolute_floor(self):
        # 10% of $0 is $0; without the floor a zero reservation could never match.
        assert classify_variance(0.0, 0.005, abs_tolerance=0.01) is SettlementStatus.MATCHED

    def test_variance_band_scales_with_the_reservation(self):
        # $50 ± 10% ⇒ $55 is inside the band, $60 is not.
        assert classify_variance(50.0, 55.0, abs_tolerance=0.01) is SettlementStatus.MATCHED
        assert classify_variance(50.0, 60.0, abs_tolerance=0.01) is SettlementStatus.OVERSPENT

    def test_underspend_is_classified_separately_from_overspend(self):
        assert classify_variance(50.0, 10.0, abs_tolerance=0.01) is SettlementStatus.UNDERSPENT

    # -- the settlement ---------------------------------------------------------------------

    def test_per_token_match_reconciles_the_provenance(self):
        s = settle(
            run_id="r", model=PER_TOKEN_MODEL, reserved_amount=6.55,
            ledger=LEDGER, date="2026-08-31", now=NOW,
        )
        assert s.status is SettlementStatus.MATCHED
        assert s.cost_source is CostSource.RECONCILED
        assert s.observed_amount == 6.60
        assert s.estimation_method == METHOD_PLATFORM_METER_DAILY
        assert s.unit == "usd"
        assert s.settled_cost_usd == 6.60
        assert s.is_reconciled

    def test_per_token_overspend_is_flagged_and_not_reconciled(self):
        s = settle(
            run_id="r", model=PER_TOKEN_MODEL, reserved_amount=1.00,
            ledger=LEDGER, date="2026-08-31", now=NOW,
        )
        assert s.status is SettlementStatus.OVERSPENT
        assert s.cost_source is CostSource.METERED
        assert s.variance == pytest.approx(5.60)
        assert not s.is_reconciled

    def test_per_token_underspend_is_recorded(self):
        s = settle(
            run_id="r", model=PER_TOKEN_MODEL, reserved_amount=100.0,
            ledger=LEDGER, date="2026-08-31", now=NOW,
        )
        assert s.status is SettlementStatus.UNDERSPENT

    def test_an_absent_meter_reading_is_unsettled_never_zero(self):
        """The load-bearing negative: no meter must not settle as "this run was free"."""
        s = settle(
            run_id="r", model=PER_TOKEN_MODEL, reserved_amount=5.0,
            ledger=None, date="2026-08-31", now=NOW,
        )
        assert s.status is SettlementStatus.UNSETTLED
        assert s.observed_amount is None
        assert s.variance is None
        assert s.cost_source is CostSource.UNKNOWN
        assert s.settled_cost_usd is None

    def test_a_missing_day_bucket_is_unsettled(self):
        s = settle(
            run_id="r", model=PER_TOKEN_MODEL, reserved_amount=5.0,
            ledger=LEDGER, date="2026-01-01", now=NOW,
        )
        assert s.status is SettlementStatus.UNSETTLED

    def test_subscription_settles_in_window_percentage_points(self):
        s = settle(
            run_id="r", model=SUBSCRIPTION_MODEL, reserved_amount=16.5,
            ledger=LEDGER, now=NOW,
        )
        assert s.status is SettlementStatus.MATCHED
        assert s.unit == "window_percent"
        assert s.observed_amount == 16.0
        # No dollars are invented for a subscription settlement.
        assert s.settled_cost_usd is None

    def test_an_unclassified_provider_is_unsettled(self):
        s = settle(run_id="r", model="acme/model", reserved_amount=5.0, ledger=LEDGER, now=NOW)
        assert s.status is SettlementStatus.UNSETTLED

    def test_settle_defaults_the_date_to_the_injected_clock(self):
        s = settle(
            run_id="r", model=PER_TOKEN_MODEL, reserved_amount=6.6, ledger=LEDGER, now=NOW
        )
        assert s.observed_amount == 6.60  # NOW is 2026-08-31

    # -- applying the settlement ------------------------------------------------------------

    def test_apply_to_upgrades_a_matched_observation_to_reconciled(self):
        before = CostObservation(
            cost_usd=6.55, source=CostSource.ESTIMATED,
            estimation_method=METHOD_TOKEN_PRICE_TABLE, reported_cost_usd=0.0,
        )
        s = settle(
            run_id="r", model=PER_TOKEN_MODEL, reserved_amount=6.55,
            ledger=LEDGER, date="2026-08-31", now=NOW,
        )
        after = s.apply_to(before)
        assert after.source is CostSource.RECONCILED
        assert after.cost_usd == 6.60
        # The backend's own report is preserved through the upgrade.
        assert after.reported_cost_usd == 0.0

    def test_apply_to_leaves_an_unsettled_observation_untouched(self):
        before = CostObservation(
            cost_usd=1.0, source=CostSource.ESTIMATED,
            estimation_method=METHOD_TOKEN_PRICE_TABLE, reported_cost_usd=None,
        )
        s = settle(
            run_id="r", model=PER_TOKEN_MODEL, reserved_amount=1.0, ledger=None, now=NOW
        )
        assert s.apply_to(before) == before

    # -- the durable record -----------------------------------------------------------------

    def test_settlement_dict_projects_the_two_ledger_fields(self):
        s = settle(
            run_id="r", model=PER_TOKEN_MODEL, reserved_amount=6.55,
            ledger=LEDGER, date="2026-08-31", now=NOW,
        )
        row = s.to_dict()
        assert row["settled_cost_usd"] == 6.60
        assert row["settlement_status"] == "matched"
        assert row["cost_source"] == "reconciled"
        # JSON-safe: the durable line must serialise without a custom encoder.
        assert json.loads(json.dumps(row))["run_id"] == "r"

    def test_record_settlement_appends_a_jsonl_line(self, tmp_path):
        s = settle(
            run_id="r", model=PER_TOKEN_MODEL, reserved_amount=6.55,
            ledger=LEDGER, date="2026-08-31", now=NOW,
        )
        path = record_settlement(s, root=tmp_path)
        assert path is not None and path.exists()
        record_settlement(s, root=tmp_path)  # append, do not overwrite
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["status"] == "matched"

    def test_load_usage_ledger_returns_none_when_absent(self, tmp_path):
        """Never raises on the run's teardown path."""
        assert load_usage_ledger(tmp_path) is None

    def test_load_usage_ledger_returns_none_on_malformed_json(self, tmp_path):
        path = tmp_path / "experiments" / "results" / "usage"
        path.mkdir(parents=True)
        (path / "subscription_usage_latest.json").write_text("{not json")
        assert load_usage_ledger(tmp_path) is None

    def test_settlement_is_frozen(self):
        """A settlement is a record of a comparison, not a mutable accumulator."""
        s = settle(run_id="r", model=PER_TOKEN_MODEL, reserved_amount=1.0, ledger=None, now=NOW)
        with pytest.raises((AttributeError, TypeError)):
            s.status = SettlementStatus.MATCHED  # type: ignore[misc]

    def test_settlement_type_is_exported(self):
        assert Settlement is not None

    # -- the wiring -------------------------------------------------------------------------

    def test_admitted_settles_the_run_on_exit_when_armed(self, monkeypatch, tmp_path):
        """The hook fires for a real run: ``admitted()`` settles before it releases.

        ``admitted`` wraps exactly the paths that ARE runs (the worker's cells, the workflow's
        phases). Asserting here rather than at each entry point is what makes the hook
        single-sited.
        """
        from unittest.mock import patch

        from agentic_dynamics.control import admission as admission_mod
        from agentic_dynamics.control.admission import AdmissionController, AdmissionRequest
        from agentic_dynamics.control.lease_registry import (
            LeaseKind,
            LeaseRegistry,
            LeaseScope,
            ScopeKind,
        )
        from agentic_dynamics.control.settlement import SETTLEMENT_ENABLED_ENV

        try:
            from tests.test_lease_registry import Clock, FakeRedis
        except ImportError:  # pragma: no cover - direct-run path
            from test_lease_registry import Clock, FakeRedis

        clock = Clock()
        counter = iter(f"{i:04d}" for i in range(1, 1000))
        registry = LeaseRegistry(FakeRedis(), now_fn=clock, id_fn=lambda: next(counter))
        deepseek = LeaseScope(ScopeKind.PROVIDER, "deepseek")
        fleet = LeaseScope(ScopeKind.FLEET, "ladder")
        registry.set_cap(LeaseKind.BUDGET, deepseek, 50.0)
        registry.set_cap(LeaseKind.CONCURRENCY, fleet, 4.0)
        controller = AdmissionController(registry, now_fn=clock)

        settled: list[dict] = []
        monkeypatch.setattr(
            admission_mod, "settle_run",
            lambda **kwargs: settled.append(kwargs) or None,
        )

        request = AdmissionRequest(
            run_id="run-ds", model=PER_TOKEN_MODEL,
            worktree_identity="wt", result_namespace="ns",
            amount=2.5, cost_source=CostSource.ESTIMATED, hard_cap_usd=10.0,
            budget_scope=deepseek, concurrency_scopes=(fleet,),
        )
        with patch.dict("os.environ", {SETTLEMENT_ENABLED_ENV: "1"}), admission_mod.admitted(
            request, controller=controller
        ):
            assert settled == [], "settlement must happen on EXIT, not on entry"

        assert len(settled) == 1
        assert settled[0]["run_id"] == "run-ds"
        assert settled[0]["model"] == PER_TOKEN_MODEL
        assert settled[0]["reserved_amount"] == 2.5

    def test_admitted_does_not_settle_when_the_hook_is_disarmed(self, monkeypatch):
        """Default posture: settlement is opt-in, so the default run path is unchanged."""
        from unittest.mock import patch

        from agentic_dynamics.control import admission as admission_mod
        from agentic_dynamics.control.admission import AdmissionController, AdmissionRequest
        from agentic_dynamics.control.lease_registry import (
            LeaseKind,
            LeaseRegistry,
            LeaseScope,
            ScopeKind,
        )
        from agentic_dynamics.control.settlement import SETTLEMENT_ENABLED_ENV

        try:
            from tests.test_lease_registry import Clock, FakeRedis
        except ImportError:  # pragma: no cover - direct-run path
            from test_lease_registry import Clock, FakeRedis

        clock = Clock()
        counter = iter(f"{i:04d}" for i in range(1, 1000))
        registry = LeaseRegistry(FakeRedis(), now_fn=clock, id_fn=lambda: next(counter))
        anthropic = LeaseScope(ScopeKind.PROVIDER, "anthropic")
        registry.set_cap(LeaseKind.BUDGET, anthropic, 100.0)
        controller = AdmissionController(registry, now_fn=clock)

        settled: list[dict] = []
        monkeypatch.setattr(
            admission_mod, "settle_run", lambda **kwargs: settled.append(kwargs) or None
        )

        request = AdmissionRequest(
            run_id="run-sub", model=SUBSCRIPTION_MODEL,
            worktree_identity="wt", result_namespace="ns",
            budget_scope=anthropic, enforce_concurrency=False,
        )
        with patch.dict("os.environ", {SETTLEMENT_ENABLED_ENV: ""}), admission_mod.admitted(
            request, controller=controller
        ):
            pass
        assert settled == []
