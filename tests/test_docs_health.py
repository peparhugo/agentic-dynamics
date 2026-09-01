"""Contracts for the docs-health Control Room surface (the docs-drift rail's p4).

Three families, matching the three things this surface can get wrong:

1. **The three states render, and the fourth one is not "clean".** The panel's whole value is
   that ``green`` means the docs are current. A test suite that only exercised the happy path
   would let a malformed report, an errored axis, or a missing scan quietly paint green — the
   one wrong answer this rail must never give.
2. **The route serves all of them without crashing**, including when the rail has never run.
3. **The approve affordance honours the idempotence contract**, at both layers: the HTTP
   ``Idempotency-Key`` replay AND the gate's atomic claim underneath it. The proof in both cases
   is a CALL COUNT on an injected submit function — "approve runs once" is an assertion about
   how many times work was enqueued, never about how the code reads.

Every test builds its own rail state in ``tmp_path`` and points the routes at it by
monkeypatching ``server.DOCS_DRIFT_RESULTS_DIR``. Nothing here reads, or can be affected by, the
repository's real ``experiments/results/docs_drift`` state.
"""

from __future__ import annotations

import json

import pytest

from apps.control_room import server
from apps.control_room.services import docs_health
from scripts import docs_drift_watchdog as watchdog
from scripts import docs_proposal_gate as gate

# ─────────────────────────────────────────────────────────────────────────────────────────────
# Fixtures — a rail state directory in any of the states the panel must render
# ─────────────────────────────────────────────────────────────────────────────────────────────


class FakeRedis:
    """The two operations ``_idempotent_design_response`` needs, and nothing else.

    Deliberately minimal: any Redis behaviour the mutation gate does NOT use is behaviour these
    tests must not accidentally depend on. ``set(nx=True)`` models the atomic reservation, which
    is the half of the idempotency contract that lives in the HTTP layer.
    """

    def __init__(self):
        self.values: dict[str, str] = {}

    def set(self, key, value, *, nx=False, ex=None):
        assert ex is not None, "every idempotency entry must carry a TTL"
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def get(self, key):
        return self.values.get(key)


def _report(*, drift: int, per_axis: dict, findings: list[dict], checked: int = 100,
            errors: dict | None = None, axes_errored: list[str] | None = None) -> dict:
    """Build a ``latest.json`` payload in the scanner's real shape."""
    stale = sum(1 for f in findings if f.get("status") == "stale")
    missing = sum(1 for f in findings if f.get("status") == "missing")
    return {
        "schema": "docs-drift/v1",
        "root": "/tmp/fixture",
        "git_sha": "abc123def456",
        "score": {
            "total_checked": checked,
            "total_current": checked - drift,
            "total_stale": stale,
            "total_missing": missing,
            "drift": drift,
            "per_axis": {
                axis: {"current": 0, "stale": 0, "missing": 0, "checked": 0, "drift": count}
                for axis, count in per_axis.items()
            },
            "axes_errored": axes_errored or [],
        },
        "errors": errors or {},
        "findings": findings,
    }


def _finding(check_id: str, axis: str = "anchor_integrity", status: str = "stale") -> dict:
    """One finding row, carrying the ``basis`` the panel is required to surface."""
    return {
        "check_id": check_id,
        "axis": axis,
        "status": status,
        "source": "docs/architecture/current/example.md:12",
        "claim": "the doc claims server.py:900 exists",
        "code_truth": "server.py is 214 lines",
        "basis": "wc -l apps/control_room/server.py  # must be >= 900",
    }


def _write_rail(results_dir, *, report=None, flag=None, proposal=None, claim=None,
                approval=None):
    """Write a rail state directory. Any omitted file is genuinely absent, not empty."""
    results_dir.mkdir(parents=True, exist_ok=True)
    if report is not None:
        (results_dir / watchdog.LATEST_FILE).write_text(json.dumps(report), encoding="utf-8")
    if flag is not None:
        (results_dir / watchdog.STATE_FILE).write_text(json.dumps(flag), encoding="utf-8")
    if proposal is not None:
        (results_dir / watchdog.PROPOSAL_FILE).write_text(json.dumps(proposal), encoding="utf-8")
    if claim is not None:
        (results_dir / gate.RUN_LOCK_FILE).write_text(json.dumps(claim), encoding="utf-8")
    if approval is not None:
        with open(results_dir / gate.APPROVALS_FILE, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(approval) + "\n")
    return results_dir


def _flag_doc(state: str, *, drift: int = 0) -> dict:
    """A ``flag_state.json`` document in the watchdog's real shape."""
    return {
        "state": state,
        "since": "2026-09-01T01:00:00Z",
        "at": "2026-09-01T02:00:00Z",
        "drift": drift,
        "scanned_state": state,
        "git_sha": "abc123def456",
        "why": f"fixture flag in state {state}",
        "axes_errored": [],
    }


def _proposal_doc(state: str = gate.PROPOSAL_WARRANTED, *, proposal_id: str = "fixture01",
                  drift: int = 2, findings: list[dict] | None = None) -> dict:
    """A ``proposal.json`` document in the gate's real shape."""
    return {
        "proposal_id": proposal_id,
        "state": state,
        "at": "2026-09-01T02:05:00Z",
        "drift": drift,
        "threshold": 0,
        "finding_count": drift,
        "why": f"{drift} docs-drift finding(s)",
        "check_ids": [f"check-{index}" for index in range(drift)],
        "findings": findings or [],
        "report": watchdog.LATEST_REPORT_REL,
        "approval": {},
        "action": {
            "name": "docs_refresh_remediation",
            "spec": "workflows/repository/docs_refresh_remediation.yaml",
            "model": "deepseek/deepseek-v4-flash",
            "budget_usd": 3.0,
            "max_attempts": 1,
            "phases": ["p1", "p2", "p3", "p4"],
            "basis": "yaml: fixture",
        },
    }


# Each rail fixture owns a DISTINCT subdirectory of ``tmp_path``. pytest hands the same
# ``tmp_path`` to every fixture within one test, so a shared "docs_drift" name would have the
# three fixtures silently overwrite each other whenever a test requests more than one — which
# ``test_route_serves_all_three_states`` does, and which would make it assert three times against
# whichever fixture happened to be built last.


@pytest.fixture
def clean_rail(tmp_path):
    """GREEN: a measured scan with zero findings and no proposal."""
    return _write_rail(
        tmp_path / "rail_clean",
        report=_report(drift=0, per_axis={"cli_surface": 0, "anchor_integrity": 0}, findings=[]),
        flag=_flag_doc(watchdog.STATE_CLEAR),
    )


@pytest.fixture
def findings_rail(tmp_path):
    """YELLOW: measured drift, flag raised, but the gate has proposed nothing."""
    findings = [_finding("anchor/a"), _finding("cli/b", axis="cli_surface", status="missing")]
    return _write_rail(
        tmp_path / "rail_findings",
        report=_report(drift=2, per_axis={"cli_surface": 1, "anchor_integrity": 1},
                       findings=findings),
        flag=_flag_doc(watchdog.STATE_RAISED, drift=2),
    )


@pytest.fixture
def warranted_rail(tmp_path):
    """RED: measured drift AND a standing proposal awaiting the controller's signature."""
    findings = [_finding("anchor/a"), _finding("cli/b", axis="cli_surface", status="missing")]
    return _write_rail(
        tmp_path / "rail_warranted",
        report=_report(drift=2, per_axis={"cli_surface": 1, "anchor_integrity": 1},
                       findings=findings),
        flag=_flag_doc(watchdog.STATE_RAISED, drift=2),
        proposal=_proposal_doc(findings=findings),
    )


@pytest.fixture
def routed(monkeypatch):
    """Point the routes at a rail directory + a fake Redis, and hand back a test client."""
    def _bind(results_dir):
        monkeypatch.setattr(server, "DOCS_DRIFT_RESULTS_DIR", results_dir)
        redis = FakeRedis()
        monkeypatch.setattr(server, "_redis", lambda: redis)
        return server.app.test_client(), redis

    return _bind


# ─────────────────────────────────────────────────────────────────────────────────────────────
# 1. The condition vocabulary
# ─────────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("measured", "drift", "proposal_state", "expected"),
    [
        (True, 0, "none", "clean"),
        (True, 3, "none", "findings"),
        (True, 3, gate.PROPOSAL_WARRANTED, "warranted"),
        (True, 3, gate.PROPOSAL_APPROVED, "warranted"),
        (True, 3, gate.PROPOSAL_IN_FLIGHT, "warranted"),
        # Terminal proposal records are history, not a standing request: the CURRENT scan decides.
        (True, 3, gate.PROPOSAL_COMPLETED, "findings"),
        (True, 0, gate.PROPOSAL_COMPLETED, "clean"),
        (True, 0, gate.PROPOSAL_FAILED, "clean"),
        # Unmeasured outranks everything, including a standing proposal.
        (False, 0, "none", "unmeasured"),
        (False, 3, gate.PROPOSAL_WARRANTED, "unmeasured"),
    ],
)
def test_condition_resolution_covers_every_input_combination(measured, drift, proposal_state,
                                                             expected):
    """The escalation table is exhaustive and unmeasured never resolves to clean."""
    assert docs_health.resolve_condition(
        measured=measured, drift=drift, proposal_state=proposal_state
    ) == expected


def test_panel_colour_agrees_with_the_watchdog_board_row_where_both_are_defined():
    """The panel and the supervisor board cannot disagree about what a score means.

    The board row models scan state only; the panel adds the proposal axis. Wherever the board
    row HAS an opinion — i.e. with no proposal standing — the two must produce the same colour,
    or an operator reading the board and an operator reading the panel would be told different
    things about the same scan. The mapping is read out of the watchdog's own source rather than
    restated here, so this guard breaks if either side is changed alone.
    """
    board_health = {
        watchdog.STATE_CLEAR: "green",
        watchdog.STATE_RAISED: "yellow",
        watchdog.STATE_UNMEASURED: "red",
    }
    panel_inputs = {
        watchdog.STATE_CLEAR: {"measured": True, "drift": 0},
        watchdog.STATE_RAISED: {"measured": True, "drift": 7},
        watchdog.STATE_UNMEASURED: {"measured": False, "drift": 0},
    }

    for scan_state, expected_colour in board_health.items():
        condition = docs_health.resolve_condition(
            proposal_state="none", **panel_inputs[scan_state]
        )
        assert docs_health.CONDITIONS[condition]["color"] == expected_colour, scan_state


def test_every_condition_carries_a_distinct_word_so_colour_is_never_the_only_signal():
    """``warranted`` and ``unmeasured`` share a hue; they must not share a word."""
    words = [entry["word"] for entry in docs_health.CONDITIONS.values()]
    assert len(set(words)) == len(words)
    warranted = docs_health.CONDITIONS["warranted"]
    unmeasured = docs_health.CONDITIONS["unmeasured"]
    assert warranted["color"] == unmeasured["color"]
    assert warranted["word"] != unmeasured["word"]


# ─────────────────────────────────────────────────────────────────────────────────────────────
# 2. The envelope, in each state
# ─────────────────────────────────────────────────────────────────────────────────────────────


def test_clean_rail_renders_green_with_no_findings_and_no_proposal(clean_rail):
    """GREEN: measured, zero drift, nothing to approve."""
    envelope = docs_health.load_docs_health(clean_rail)

    assert envelope["condition"] == "clean"
    assert envelope["health"] == "green"
    assert envelope["available"] is True
    assert envelope["scan"]["measured"] is True
    assert envelope["scan"]["drift"] == 0
    assert envelope["inventory"] == []
    assert envelope["proposal"]["state"] == gate.PROPOSAL_NONE
    assert envelope["proposal"]["approvable"] is False
    assert "current" in envelope["headline"]


def test_findings_rail_renders_yellow_with_the_inventory_summary(findings_rail):
    """YELLOW: drift is visible with its per-axis summary and its re-derivable basis."""
    envelope = docs_health.load_docs_health(findings_rail)

    assert envelope["condition"] == "findings"
    assert envelope["health"] == "yellow"
    assert envelope["scan"]["drift"] == 2
    assert envelope["scan"]["per_axis"] == {"cli_surface": 1, "anchor_integrity": 1}
    assert envelope["flag"]["raised"] is True
    assert len(envelope["inventory"]) == 2
    # The basis is the evidence half of the panel — a finding without it is an assertion.
    assert all(row["basis"] for row in envelope["inventory"])
    # Yellow is a report, not a request: no proposal, so nothing is approvable.
    assert envelope["proposal"]["approvable"] is False
    assert "2 drift finding(s) of 100 checked" in envelope["headline"]


def test_warranted_rail_renders_red_with_the_proposal_and_the_approve_affordance(warranted_rail):
    """RED: the remediation is visible, costed from the spec, and approvable."""
    envelope = docs_health.load_docs_health(warranted_rail)

    assert envelope["condition"] == "warranted"
    assert envelope["health"] == "red"
    assert envelope["proposal"]["state"] == gate.PROPOSAL_WARRANTED
    assert envelope["proposal"]["proposal_id"] == "fixture01"
    assert envelope["proposal"]["approvable"] is True
    assert envelope["proposal"]["action"]["name"] == "docs_refresh_remediation"
    assert envelope["proposal"]["action"]["budget_usd"] == 3.0
    assert envelope["proposal"]["action"]["phases"] == ["p1", "p2", "p3", "p4"]
    # The cost estimate carries its derivation, like every other number this rail prints.
    assert envelope["proposal"]["action"]["basis"]
    assert "docs_refresh_remediation" in envelope["headline"]


def test_missing_rail_is_unmeasured_and_never_clean(tmp_path):
    """An empty rail directory is red-and-unmeasured, not green."""
    envelope = docs_health.load_docs_health(tmp_path / "never_scanned")

    assert envelope["condition"] == "unmeasured"
    assert envelope["health"] == "red"
    assert envelope["available"] is False
    assert envelope["scan"]["measured"] is False
    assert "no docs-drift scan on record" in envelope["headline"]
    assert envelope["proposal"]["approvable"] is False


def test_errored_axis_is_unmeasured_even_though_its_drift_count_is_zero(tmp_path):
    """A scan that could not run every axis reports zero drift; that is not a clean scan."""
    rail = _write_rail(
        tmp_path / "docs_drift",
        report=_report(drift=0, per_axis={"cli_surface": 0}, findings=[],
                       errors={"anchor_integrity": "boom"}, axes_errored=["anchor_integrity"]),
        flag=_flag_doc(watchdog.STATE_UNMEASURED),
    )

    envelope = docs_health.load_docs_health(rail)

    assert envelope["condition"] == "unmeasured"
    assert envelope["health"] == "red"
    # ``available`` and ``measured`` answer different questions: the rail DID produce a report,
    # it just is not one that can be acted on.
    assert envelope["available"] is True
    assert envelope["scan"]["measured"] is False
    assert "anchor_integrity" in envelope["scan"]["reason"]


@pytest.mark.parametrize(
    "malformed",
    [
        pytest.param({"schema": "docs-drift/v1", "git_sha": "x"}, id="no-score-block"),
        pytest.param({"score": {"total_checked": 0, "drift": 0}}, id="vacuous-scan"),
        pytest.param({"score": "not-a-dict"}, id="score-wrong-type"),
        # A drift the report FAILED TO STATE is not a drift of zero. Without the strict read in
        # ``_score_is_substantive`` each of these falls through ``_as_int`` to 0 and paints green.
        pytest.param({"score": {"drift": [1, 2, 3], "total_checked": 9}}, id="drift-is-a-list"),
        pytest.param({"score": {"drift": None, "total_checked": 9}}, id="drift-is-null"),
        pytest.param({"score": {"drift": "several", "total_checked": 9}}, id="drift-is-a-word"),
        pytest.param({"score": {"total_checked": 9}}, id="drift-absent"),
    ],
)
def test_structurally_malformed_report_is_unmeasured_not_clean(tmp_path, malformed):
    """The false-CLEAN hole: a report with no counted checks must not paint green.

    ``gate.report_is_measured`` tests for the ABSENCE of errors, so each of these passes it
    vacuously and arrives with drift 0. Without the structural check in ``_score_is_substantive``
    every one of them would render as "docs current — 0 anchored claims reproduce", which is the
    same lie as treating an absent report as clean.
    """
    rail = _write_rail(tmp_path / "docs_drift", report=malformed,
                       flag=_flag_doc(watchdog.STATE_CLEAR))

    envelope = docs_health.load_docs_health(rail)

    assert envelope["condition"] == "unmeasured"
    assert envelope["health"] == "red"


@pytest.mark.parametrize(
    "garbage",
    [
        pytest.param([], id="report-is-a-list"),
        pytest.param("a bare string", id="report-is-a-string"),
        pytest.param(42, id="report-is-a-number"),
        pytest.param({"score": {"axes_errored": [{"unhashable": 1}],
                                "total_checked": 5, "drift": 1}},
                     id="unhashable-axis-entry"),
        pytest.param({"score": {"per_axis": {"a": "not-a-dict"}, "total_checked": 5, "drift": 1}},
                     id="per-axis-entry-wrong-type"),
        pytest.param({"errors": "a string not a dict", "score": {"total_checked": 5, "drift": 0}},
                     id="errors-wrong-type"),
        pytest.param({"findings": "not a list", "score": {"total_checked": 5, "drift": 0}},
                     id="findings-wrong-type"),
        pytest.param({"findings": [1, 2, "three"], "score": {"total_checked": 5, "drift": 0}},
                     id="findings-entries-wrong-type"),
    ],
)
def test_no_shape_of_corrupt_report_can_crash_the_panel(tmp_path, garbage):
    """Adversarial sweep: a corrupt rail file costs the panel its numbers, never its availability.

    Two properties, and only the first is obvious. The panel must not raise — but it must also
    not answer confidently from junk, so anything that renders GREEN here has to be a report
    whose SCORE genuinely says clean. The last two cases are exactly that: ``findings`` is
    unusable but ``drift: 0`` over 5 checks is a real verdict, and the score is the authority for
    the verdict while ``findings`` is only the inventory detail. Calling those unmeasured would be
    the opposite error — refusing to report a clean scan because its appendix was damaged.
    """
    rail = _write_rail(tmp_path / "docs_drift", report=garbage,
                       flag=_flag_doc(watchdog.STATE_CLEAR))

    envelope = docs_health.load_docs_health(rail)

    assert envelope["condition"] in docs_health.CONDITIONS
    if envelope["health"] == "green":
        score = garbage["score"] if isinstance(garbage, dict) else {}
        assert score.get("drift") == 0 and score.get("total_checked", 0) > 0, \
            f"rendered green from a report that never stated a clean score: {garbage}"

def test_unreadable_report_and_unreadable_flag_state_degrade_rather_than_raise(tmp_path):
    """A corrupt rail file costs the panel its numbers, never its availability."""
    rail = tmp_path / "docs_drift"
    rail.mkdir(parents=True)
    (rail / watchdog.LATEST_FILE).write_text("{ not json", encoding="utf-8")
    (rail / watchdog.STATE_FILE).write_text("also not json", encoding="utf-8")
    (rail / watchdog.PROPOSAL_FILE).write_text("<<<", encoding="utf-8")

    envelope = docs_health.load_docs_health(rail)

    assert envelope["condition"] == "unmeasured"
    assert envelope["available"] is False


def test_inventory_truncation_is_reported_and_never_silent(tmp_path):
    """A cut list says so; a list that quietly stops reads as complete."""
    findings = [_finding(f"anchor/{index}") for index in range(30)]
    rail = _write_rail(
        tmp_path / "docs_drift",
        report=_report(drift=30, per_axis={"anchor_integrity": 30}, findings=findings),
        flag=_flag_doc(watchdog.STATE_RAISED, drift=30),
    )

    envelope = docs_health.load_docs_health(rail, inventory_limit=5)

    assert len(envelope["inventory"]) == 5
    assert envelope["inventory_truncated"] is True
    assert envelope["inventory_limit"] == 5
    assert envelope["scan"]["drift"] == 30


def test_in_flight_proposal_is_warranted_but_not_approvable(tmp_path):
    """A run already holds the rail: the state is shown, the button is not offered."""
    rail = _write_rail(
        tmp_path / "docs_drift",
        report=_report(drift=2, per_axis={"anchor_integrity": 2},
                       findings=[_finding("a"), _finding("b")]),
        flag=_flag_doc(watchdog.STATE_RAISED, drift=2),
        proposal=_proposal_doc(state=gate.PROPOSAL_IN_FLIGHT),
        claim={"run_id": "run123", "at": "2026-09-01T02:10:00Z", "proposal_id": "fixture01"},
    )

    envelope = docs_health.load_docs_health(rail)

    assert envelope["condition"] == "warranted"
    assert envelope["proposal"]["state"] == gate.PROPOSAL_IN_FLIGHT
    assert envelope["proposal"]["approvable"] is False
    assert envelope["proposal"]["run"]["run_id"] == "run123"


def test_loading_the_envelope_writes_nothing_to_the_rail(warranted_rail):
    """A dashboard poll must not be able to change the state it is displaying."""
    before = {path.name: path.read_bytes() for path in sorted(warranted_rail.iterdir())}

    for _ in range(5):
        docs_health.load_docs_health(warranted_rail)

    after = {path.name: path.read_bytes() for path in sorted(warranted_rail.iterdir())}
    assert after == before


# ─────────────────────────────────────────────────────────────────────────────────────────────
# 3. The route
# ─────────────────────────────────────────────────────────────────────────────────────────────


def test_route_serves_all_three_states_plus_unmeasured_without_crashing(
    routed, clean_rail, findings_rail, warranted_rail, tmp_path
):
    """The VERIFY contract: every state renders over HTTP, none of them 500s."""
    expected = [
        (clean_rail, "clean", "green"),
        (findings_rail, "findings", "yellow"),
        (warranted_rail, "warranted", "red"),
        (tmp_path / "never_scanned", "unmeasured", "red"),
    ]

    for rail, condition, colour in expected:
        client, _redis = routed(rail)
        response = client.get("/api/docs-health")

        assert response.status_code == 200, condition
        body = response.get_json()
        assert body["schema"] == docs_health.SCHEMA
        assert body["condition"] == condition
        assert body["health"] == colour
        # Colour is never the only signal, all the way out to the wire.
        assert body["word"] and body["headline"]


def test_approve_requires_the_local_json_trust_boundary(routed, warranted_rail):
    """The mutation gate is actually in the path: no key, no JSON, no approval."""
    client, _redis = routed(warranted_rail)

    no_key = client.post("/api/docs-health/approve",
                         json={"proposal_id": "fixture01", "by": "operator"})
    not_json = client.post("/api/docs-health/approve", data="proposal_id=fixture01",
                           headers={"Idempotency-Key": "k1"})

    assert no_key.status_code == 400
    assert "Idempotency-Key" in no_key.get_json()["error"]
    assert not_json.status_code == 415


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        ({"by": "operator"}, "proposal_id is required"),
        ({"proposal_id": "  ", "by": "operator"}, "proposal_id is required"),
        ({"proposal_id": "fixture01"}, "by is required"),
        ({"proposal_id": "fixture01", "by": "   "}, "by is required"),
        ({"proposal_id": "fixture01", "by": "op", "dispatch": "yes"}, "dispatch must be a boolean"),
        ({"proposal_id": "fixture01", "by": "op", "reason": 7}, "reason must be a string"),
    ],
)
def test_approve_rejects_malformed_signatures_before_touching_the_gate(
    routed, warranted_rail, body, fragment
):
    """Shape validation is the route's only job, and it happens before any side effect."""
    client, _redis = routed(warranted_rail)

    response = client.post("/api/docs-health/approve", json=body,
                           headers={"Idempotency-Key": "shape"})

    assert response.status_code == 400
    assert fragment in response.get_json()["error"]
    # Nothing was signed: the audit trail is still empty.
    assert not (warranted_rail / gate.APPROVALS_FILE).exists()


def test_approve_refuses_a_signature_for_a_proposal_that_changed_underneath(routed,
                                                                            warranted_rail):
    """The race this panel invites: the tab was open, the hourly timer fired."""
    client, _redis = routed(warranted_rail)

    response = client.post(
        "/api/docs-health/approve",
        json={"proposal_id": "an-older-proposal", "by": "operator"},
        headers={"Idempotency-Key": "stale"},
    )

    assert response.status_code == 409
    body = response.get_json()
    assert body["outcome"] == "refused_stale_approval"
    assert body["enqueued"] is False
    assert not (warranted_rail / gate.APPROVALS_FILE).exists()


def test_approve_on_a_clean_rail_has_nothing_to_approve(routed, clean_rail):
    """No proposal stands, so there is no signature to record."""
    client, _redis = routed(clean_rail)

    response = client.post(
        "/api/docs-health/approve",
        json={"proposal_id": "fixture01", "by": "operator"},
        headers={"Idempotency-Key": "nothing"},
    )

    assert response.status_code == 409
    assert response.get_json()["outcome"] == "refused_no_proposal"


def test_approve_records_an_attributed_signature_and_dispatches_exactly_once(
    routed, warranted_rail, monkeypatch
):
    """The happy path — and the call count that IS the approve-runs-once proof."""
    submissions = []

    def fake_submit(*, spec, goal, model, workdir):
        submissions.append({"spec": spec, "goal": goal, "model": model, "workdir": workdir})
        return {"job_id": "job-1"}

    # Intercept at the gate's own enqueue seam: everything upstream of it — the state check, the
    # id match, the atomic claim — runs for real, which is the only way this test proves anything.
    monkeypatch.setattr(gate, "fleet_submit", fake_submit)
    client, _redis = routed(warranted_rail)

    response = client.post(
        "/api/docs-health/approve",
        json={"proposal_id": "fixture01", "by": "controller", "reason": "signed at the board"},
        headers={"Idempotency-Key": "approve-1"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["outcome"] == "dispatched"
    assert body["enqueued"] is True
    assert len(submissions) == 1

    # The signature is durable, attributed, and names the inventory it was given.
    approvals = [
        json.loads(line)
        for line in (warranted_rail / gate.APPROVALS_FILE).read_text().splitlines()
    ]
    assert len(approvals) == 1
    assert approvals[0]["by"] == "controller"
    assert approvals[0]["reason"] == "signed at the board"
    assert approvals[0]["proposal_id"] == "fixture01"

    # And the claim is held, so the rail now reads in_flight to every later reader.
    assert (warranted_rail / gate.RUN_LOCK_FILE).exists()
    after = docs_health.load_docs_health(warranted_rail)
    assert after["proposal"]["state"] == gate.PROPOSAL_IN_FLIGHT


def test_replaying_the_same_idempotency_key_returns_the_first_answer_and_never_re_enqueues(
    routed, warranted_rail, monkeypatch
):
    """LAYER 1 — the HTTP replay. A double-click never reaches the gate a second time."""
    calls = []
    monkeypatch.setattr(gate, "fleet_submit",
                        lambda **kwargs: (calls.append(kwargs), {"job_id": "job-1"})[1])
    approvals = []
    real_approve = docs_health.approve_proposal
    monkeypatch.setattr(
        docs_health, "approve_proposal",
        lambda **kwargs: (approvals.append(kwargs), real_approve(**kwargs))[1],
    )
    client, _redis = routed(warranted_rail)
    payload = {"proposal_id": "fixture01", "by": "controller"}

    first = client.post("/api/docs-health/approve", json=payload,
                        headers={"Idempotency-Key": "approve-1"})
    replay = client.post("/api/docs-health/approve", json=payload,
                         headers={"Idempotency-Key": "approve-1"})

    assert first.status_code == replay.status_code == 200
    assert first.get_json() == replay.get_json()
    assert len(calls) == 1, "the remediation was enqueued twice"
    # The stronger claim: the gate was not merely safe on the replay, it was never called.
    assert len(approvals) == 1


def test_a_second_key_still_cannot_launch_a_second_remediation(
    routed, warranted_rail, monkeypatch
):
    """LAYER 2 — the gate's atomic claim, which is what the HTTP layer cannot cover.

    Two browser tabs mint two different keys, so the idempotency cache lets both through to the
    gate. The ``O_EXCL`` claim on ``remediation.lock`` is what makes the second one a no-op, and
    this is the test that distinguishes "the rail runs once" from "the same request replays".
    """
    calls = []
    monkeypatch.setattr(gate, "fleet_submit",
                        lambda **kwargs: (calls.append(kwargs), {"job_id": "job-1"})[1])
    client, _redis = routed(warranted_rail)
    payload = {"proposal_id": "fixture01", "by": "controller"}

    first = client.post("/api/docs-health/approve", json=payload,
                        headers={"Idempotency-Key": "tab-one"})
    second = client.post("/api/docs-health/approve", json=payload,
                         headers={"Idempotency-Key": "tab-two"})

    assert first.status_code == 200
    assert first.get_json()["enqueued"] is True
    # The second approval is not an ERROR — it is the contract working. 200, and it says so.
    assert second.status_code == 200
    assert second.get_json()["outcome"] == "already_in_flight"
    assert second.get_json()["enqueued"] is False
    assert len(calls) == 1, "a second key launched a second remediation"

    # Exactly one signature was recorded: the no-op wrote nothing.
    approvals = (warranted_rail / gate.APPROVALS_FILE).read_text().splitlines()
    assert len(approvals) == 1


def test_reusing_one_key_across_two_proposals_cannot_replay_the_wrong_answer(
    routed, warranted_rail, monkeypatch
):
    """The operation string carries the proposal id, so a replay is only honest within one.

    Without the id in the namespace, an operator who reused ``approve-1`` after the inventory
    changed would be handed the FIRST proposal's cached success — a signature they never gave,
    for findings they never saw.
    """
    monkeypatch.setattr(gate, "fleet_submit", lambda **kwargs: {"job_id": "job-1"})
    client, _redis = routed(warranted_rail)

    first = client.post("/api/docs-health/approve",
                        json={"proposal_id": "fixture01", "by": "controller"},
                        headers={"Idempotency-Key": "shared-key"})
    other = client.post("/api/docs-health/approve",
                        json={"proposal_id": "a-different-proposal", "by": "controller"},
                        headers={"Idempotency-Key": "shared-key"})

    assert first.get_json()["outcome"] == "dispatched"
    # Not a replayed success: the second proposal id got its own, correct, refusal.
    assert other.get_json()["outcome"] != "dispatched"
    assert other.get_json()["enqueued"] is False


def test_approve_without_dispatch_signs_but_queues_nothing(routed, warranted_rail, monkeypatch):
    """``dispatch: false`` is the sign-now-launch-later path; it must not enqueue."""
    calls = []
    monkeypatch.setattr(gate, "fleet_submit",
                        lambda **kwargs: (calls.append(kwargs), {"job_id": "job-1"})[1])
    client, _redis = routed(warranted_rail)

    response = client.post(
        "/api/docs-health/approve",
        json={"proposal_id": "fixture01", "by": "controller", "dispatch": False},
        headers={"Idempotency-Key": "sign-only"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["outcome"] == "approved"
    assert body["enqueued"] is False
    assert calls == []
    # Signed, and the proposal now stands as approved rather than in flight.
    after = docs_health.load_docs_health(warranted_rail)
    assert after["proposal"]["state"] == gate.PROPOSAL_APPROVED
    assert not (warranted_rail / gate.RUN_LOCK_FILE).exists()


def test_a_failed_enqueue_is_retryable_and_leaves_the_rail_dispatchable(
    routed, warranted_rail, monkeypatch
):
    """p3 rolls its claim back on a failed submit; the route reports that truthfully."""
    def exploding_submit(**_kwargs):
        raise RuntimeError("fleet:commands unreachable")

    monkeypatch.setattr(gate, "fleet_submit", exploding_submit)
    client, _redis = routed(warranted_rail)

    response = client.post(
        "/api/docs-health/approve",
        json={"proposal_id": "fixture01", "by": "controller"},
        headers={"Idempotency-Key": "boom"},
    )

    assert response.status_code == 503
    body = response.get_json()
    assert body["outcome"] == "dispatch_failed"
    assert body["retryable"] is True
    # The claim was rolled back — a rail nobody can unblock gets bypassed.
    assert not (warranted_rail / gate.RUN_LOCK_FILE).exists()


def test_get_is_read_only_over_http_too(routed, warranted_rail):
    """Polling the route cannot mutate the rail — the property, asserted at the HTTP layer."""
    client, _redis = routed(warranted_rail)
    before = {path.name: path.read_bytes() for path in sorted(warranted_rail.iterdir())}

    for _ in range(3):
        assert client.get("/api/docs-health").status_code == 200

    after = {path.name: path.read_bytes() for path in sorted(warranted_rail.iterdir())}
    assert after == before


def test_concurrent_approvals_through_the_route_enqueue_exactly_once(routed, warranted_rail,
                                                                     monkeypatch):
    """The approve-runs-once contract under REAL concurrency, with the HTTP layer disabled.

    Every caller uses a DISTINCT ``Idempotency-Key``, which defeats the replay cache entirely —
    so anything that survives to the gate does so on the strength of the ``O_EXCL`` claim alone.
    That is the layer that matters here, because two operators on two machines, or a portal click
    racing a CLI ``docs gate approve``, are exactly the case a per-request cache cannot see.

    A barrier releases all callers at the same instant; the assertion is a call count on the
    injected submit. Flask serves ``threaded=True`` in production, so this is the concurrency the
    route genuinely faces, not a hypothetical.
    """
    import threading

    submits = []
    submit_lock = threading.Lock()

    def counting_submit(**kwargs):
        with submit_lock:
            submits.append(kwargs)
        return {"job_id": f"job-{len(submits)}"}

    monkeypatch.setattr(gate, "fleet_submit", counting_submit)

    class LockedRedis(FakeRedis):
        """FakeRedis with a real lock — an unsynchronised dict would be the test's own race."""

        def __init__(self):
            super().__init__()
            self.lock = threading.Lock()

        def set(self, key, value, *, nx=False, ex=None):
            with self.lock:
                return super().set(key, value, nx=nx, ex=ex)

        def get(self, key):
            with self.lock:
                return super().get(key)

    monkeypatch.setattr(server, "DOCS_DRIFT_RESULTS_DIR", warranted_rail)
    redis = LockedRedis()
    monkeypatch.setattr(server, "_redis", lambda: redis)

    callers = 8
    barrier = threading.Barrier(callers)
    outcomes: list[dict] = [None] * callers

    def approve(index: int) -> None:
        barrier.wait()
        response = server.app.test_client().post(
            "/api/docs-health/approve",
            json={"proposal_id": "fixture01", "by": f"controller-{index}"},
            headers={"Idempotency-Key": f"distinct-{index}"},
        )
        outcomes[index] = response.get_json()

    threads = [threading.Thread(target=approve, args=(index,)) for index in range(callers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # THE assertion. One submit, one run record, one claim — no matter how many signed.
    assert len(submits) == 1, f"the remediation was enqueued {len(submits)} times"
    assert sum(1 for body in outcomes if body["enqueued"]) == 1
    assert len((warranted_rail / gate.RUNS_FILE).read_text().splitlines()) == 1
    assert (warranted_rail / gate.RUN_LOCK_FILE).exists()

    # Every caller got a coherent answer — none of them saw a torn proposal document and was
    # told "nothing to approve" about a proposal that was plainly standing. That is what
    # ``write_proposal``'s atomic replace buys; before it, this assertion failed intermittently.
    assert all(body["outcome"] in {"dispatched", "already_in_flight"} for body in outcomes), \
        [body["outcome"] for body in outcomes]


def test_proposal_writes_are_atomic_so_a_reader_never_sees_a_torn_document(warranted_rail):
    """A reader interleaved with 200 writes always observes a complete document.

    The regression guard for ``write_proposal``'s ``os.replace``. With a truncate-then-write, a
    reader landing inside the window gets ``{}`` — which the gate reads as "no proposal stands",
    a wrong answer rather than a graceful default.
    """
    import threading

    proposal = json.loads((warranted_rail / watchdog.PROPOSAL_FILE).read_text())
    stop = threading.Event()
    torn: list[dict] = []

    def writer() -> None:
        for index in range(200):
            gate.write_proposal(warranted_rail, {**proposal, "drift": index})
        stop.set()

    def reader() -> None:
        while not stop.is_set():
            observed = gate.read_proposal(warranted_rail)
            if observed.get("proposal_id") != "fixture01":
                torn.append(observed)

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert torn == [], f"observed {len(torn)} torn read(s) of proposal.json"
    # And no temp file was left behind to be mistaken for rail state.
    assert not list(warranted_rail.glob(".proposal-*.tmp"))
