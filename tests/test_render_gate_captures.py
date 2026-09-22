"""Render-gate capture tests — the zero-captures rejection (remediation closed-loop, decision
f987cde9).

The 2026-09-13 failure class: a workflow's verify phase passed while its committed gate report
read "PASS, Screenshots: 0" — acceptance without rendered proof. The rule is now structural in
``write_report``: a gate run that recorded no capture is a FAIL with a named violation, whatever
the fixture checks say. These tests exercise ``write_report`` directly (the pure report
assembly — no browser), plus the live-gate plumbing that feeds it.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.verify_control_room_rendering import write_report


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "gate_report.md", tmp_path / "gate_report.json"


def test_write_report_fails_on_zero_captures(tmp_path: Path):
    """A PASS with no captures is structurally impossible — the report says so, loudly."""
    report, jp = _paths(tmp_path)
    rc = write_report([], [], report, jp, check_fixtures_exit=0)
    assert rc == 1
    text = report.read_text(encoding="utf-8")
    assert "**Status:** FAIL" in text
    assert "GATE-CAPTURES" in text, "the zero-captures violation is named, not implied"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["status"] == "FAIL"
    assert any("GATE-CAPTURES" in e for e in data["errors"])


def test_write_report_fails_on_zero_captures_even_when_fixtures_pass(tmp_path: Path):
    """The fixture sub-check passing cannot rescue an unrendered gate — captures are the proof."""
    report, jp = _paths(tmp_path)
    rc = write_report([], [], report, jp, check_fixtures_exit=0)
    assert rc == 1
    assert "**Screenshots:** 0 (none)" in report.read_text(encoding="utf-8")
    assert "GATE-CAPTURES" in report.read_text(encoding="utf-8")


def test_write_report_passes_with_captures_and_no_errors(tmp_path: Path):
    """The positive half: a gate that rendered proof and found no violations passes."""
    report, jp = _paths(tmp_path)
    results = [{"screenshot": "s1.png", "case": "F-0", "viewport": "desktop"}]
    rc = write_report(results, [], report, jp, check_fixtures_exit=0)
    assert rc == 0
    assert "**Status:** PASS" in report.read_text(encoding="utf-8")
    assert "GATE-CAPTURES" not in report.read_text(encoding="utf-8")


def test_write_report_still_fails_on_errors_with_captures(tmp_path: Path):
    """Captures are necessary, not sufficient — a rendered failure is still a failure."""
    report, jp = _paths(tmp_path)
    results = [{"screenshot": "s1.png", "case": "F-0", "viewport": "desktop"}]
    rc = write_report(results, ["G-2 page scrollWidth 200 > 100"], report, jp, check_fixtures_exit=0)
    assert rc == 1
    assert "**Status:** FAIL" in report.read_text(encoding="utf-8")


# ── The acceptance profile contract (AIO remediation 2026-09-14) ─────────────


def test_write_report_prints_declared_coverage_only(tmp_path: Path):
    """The 2026-09-18 review: the restored profile's report must not inherit the parked
    profile's mobile/forced-colors/contrast/first-paint claims. Declared coverage prints
    verbatim; a claim that was not declared is not printed."""
    report, jp = _paths(tmp_path)
    results = [
        {
            "screenshot": "s1.png",
            "case": "boards-navigation",
            "viewport": "desktop",
            "theme": "dark",
        }
    ]
    coverage = {
        "performed": ["navigation: seven destinations"],
        "omitted": ["mobile viewport (390x844)"],
    }
    rc = write_report(
        results,
        [],
        report,
        jp,
        0,
        requested_classes=["navigation"],
        coverage=coverage,
    )
    assert rc == 0
    text = report.read_text(encoding="utf-8")
    assert "**Coverage executed:** navigation: seven destinations" in text
    assert "**Coverage omitted:** mobile viewport (390x844)" in text
    assert "**Viewports exercised:** desktop" in text
    assert "**Themes exercised:** dark" in text
    assert "WCAG-AA contrast" not in text, "a claim the run did not execute was printed"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["coverage"]["omitted"] == ["mobile viewport (390x844)"]


def test_write_report_keeps_legacy_lines_without_a_coverage_declaration(tmp_path: Path):
    """Legacy parked runs keep their own documented coverage lines; the restored declaration
    is never assumed on their behalf."""
    report, jp = _paths(tmp_path)
    results = [{"screenshot": "s1.png", "case": "F-0", "viewport": "desktop"}]
    rc = write_report(results, [], report, jp, 0)
    assert rc == 0
    text = report.read_text(encoding="utf-8")
    assert "**Viewports:**" in text
    assert "Coverage executed" not in text
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["coverage"] == {}


def test_write_report_names_an_omitted_required_class(tmp_path: Path):
    """The profile's omission rule: a requested class that produced no results is a NAMED
    fail — never a silent skip (--live alone cannot claim the profile ran)."""
    report, jp = _paths(tmp_path)
    results = [{"screenshot": "s1.png", "case": "F-0", "viewport": "desktop"}]
    rc = write_report(results, [], report, jp, check_fixtures_exit=0,
                      requested_classes=["geometry", "charts", "live"])
    assert rc == 1
    text = report.read_text(encoding="utf-8")
    assert "**Status:** FAIL" in text
    assert "PROFILE-OMITTED" in text and "charts" in text and "live" in text
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["requested_classes"] == ["geometry", "charts", "live"]
    assert data["executed_classes"] == ["geometry"]


def test_write_report_binds_the_candidate_and_preview(tmp_path: Path):
    """The verdict describes exactly what was reviewed: candidate SHA + preview target ride
    both artifacts, so a capture set can never be re-attributed to another candidate."""
    report, jp = _paths(tmp_path)
    results = [{"screenshot": "s1.png", "case": "F-0", "viewport": "desktop"}]
    rc = write_report(results, [], report, jp, check_fixtures_exit=0,
                      requested_classes=["geometry"],
                      candidate="deadbeef1234", preview="http://127.0.0.1:8123/")
    assert rc == 0
    assert "**Candidate:** deadbeef1234" in report.read_text(encoding="utf-8")
    assert "**Preview target:** http://127.0.0.1:8123/" in report.read_text(encoding="utf-8")
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["candidate"] == "deadbeef1234"
    assert data["preview"] == "http://127.0.0.1:8123/"


def test_verify_captures_refuses_missing_or_empty_files(tmp_path: Path):
    """A nonempty screenshot LIST is not acceptance: a capture that does not exist (or is
    empty) is a named GATE-CAPTURE-UNREADABLE error."""
    from scripts.verify_control_room_rendering import _verify_captures

    good = tmp_path / "good.png"
    good.write_bytes(b"\x89PNG")
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    errors = _verify_captures([
        {"screenshot": str(good)},
        {"screenshot": str(empty)},
        {"screenshot": str(tmp_path / "missing.png")},
        {"screenshot": ""},
    ])
    assert len(errors) == 2
    assert all("GATE-CAPTURE-UNREADABLE" in e for e in errors)
    assert _verify_captures([{"screenshot": str(good)}]) == []


def test_write_report_labels_verified_and_unverified_identities(tmp_path: Path):
    """Astra finding: supplied labels are not verified identities. The report must SAY which
    it is — verified candidate, unexercised preview."""
    report, jp = _paths(tmp_path)
    results = [{"screenshot": "s1.png", "case": "F-0", "viewport": "desktop"}]
    rc = write_report(results, [], report, jp, check_fixtures_exit=0,
                      requested_classes=["geometry"],
                      candidate="deadbeef", candidate_verified=True,
                      preview="http://127.0.0.1:8123/", preview_verified=False,
                      preview_exercised=False)
    assert rc == 0
    text = report.read_text(encoding="utf-8")
    assert "**Candidate:** deadbeef (verified against the checkout HEAD)" in text
    assert "NOT exercised" in text
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["candidate_verified"] is True
    assert data["preview_verified"] is False
    assert data["preview_exercised"] is False


def test_write_report_labels_an_unverified_candidate(tmp_path: Path):
    """A candidate that does not match the checkout is labelled UNVERIFIED — never silently
    claimed as the reviewed candidate."""
    report, jp = _paths(tmp_path)
    results = [{"screenshot": "s1.png", "case": "F-0", "viewport": "desktop"}]
    rc = write_report(results, [], report, jp, check_fixtures_exit=0,
                      requested_classes=["geometry"],
                      candidate="deadbeef", candidate_verified=False)
    assert rc == 0
    assert "UNVERIFIED" in report.read_text(encoding="utf-8")
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["candidate_verified"] is False


# ── Reviewer reproductions (2026-09-14): the acceptance checks must prove their claims ──────


def test_canonical_preview_target_refuses_conflicting_urls():
    """The browser rendered --base while the identity checks fetched --preview: different
    URLs could produce a PASS claiming a target no browser visited. Conflicting targets are
    refused; a lone --base IS the exercised target; a lone --preview stays unexercised."""
    from scripts.verify_control_room_rendering import _canonical_preview_target

    target, error = _canonical_preview_target("http://127.0.0.1:8123/", "http://127.0.0.1:8123")
    assert target == "http://127.0.0.1:8123" and error == ""  # normalized equal

    target, error = _canonical_preview_target("http://a:1/", "http://b:2/")
    assert target == "" and "conflicting targets" in error

    target, error = _canonical_preview_target("http://127.0.0.1:8123/", None)
    assert target == "http://127.0.0.1:8123" and error == ""

    target, error = _canonical_preview_target(None, "http://127.0.0.1:8123/")
    assert target == "http://127.0.0.1:8123" and error == ""

    target, error = _canonical_preview_target(None, None)
    assert target == "" and error == ""


def test_compare_served_assets_catches_stale_js_and_binds_committed_bytes(tmp_path, monkeypatch):
    """Reviewer finding: matching CSS alone certified the preview even when the app served
    stale JS, and the comparison read the working tree. Every committed artifact is compared,
    against ``git show HEAD:`` (committed bytes)."""
    import functools
    import http.server
    import socketserver
    import subprocess
    import threading

    from scripts.verify_control_room_rendering import _compare_served_assets

    repo = tmp_path / "repo"
    static = repo / "apps" / "control_room" / "static"
    static.mkdir(parents=True)
    files = {
        "index.html": b"<html>shell v2</html>",
        "app.js": b"console.log('v2')",
        "style.css": b"body { color: red }",
    }
    for name, data in files.items():
        (static / name).write_bytes(data)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    # The working tree diverges AFTER the commit — the committed bytes are the candidate.
    (static / "style.css").write_bytes(b"body { color: blue }  /* uncommitted edit */")

    served = tmp_path / "served"
    (served / "static").mkdir(parents=True)
    (served / "index.html").write_bytes(files["index.html"])
    (served / "static" / "app.js").write_bytes(files["app.js"])
    (served / "static" / "style.css").write_bytes(files["style.css"])
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(served))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        monkeypatch.chdir(repo)
        base = f"http://127.0.0.1:{port}"
        matched = _compare_served_assets(base)
        # committed-vs-served matches for ALL artifacts; the uncommitted working-tree edit
        # must NOT be attributed to HEAD (style.css compares against the committed bytes).
        assert matched == {"index.html": True, "app.js": True, "style.css": True}

        # The reviewer's stale-JS case: CSS matches, JS is stale → caught, not certified.
        (served / "static" / "app.js").write_bytes(b"console.log('v1 stale')")
        matched = _compare_served_assets(base)
        assert matched["app.js"] is False
        assert matched["style.css"] is True
    finally:
        httpd.shutdown()


class _FakeRefreshPage:
    """A Playwright-page double for ``_exercise_refresh_action`` (missing / inert / no-op /
    working controls), so the decision logic is regression-testable without a browser."""

    def __init__(self, *, present: bool = True, works: bool = True, re_renders: bool = True):
        self.present = present
        self.works = works
        self.re_renders = re_renders
        self.finder_value = "sentinel"

    def locator(self, selector: str):
        page = self

        if selector == "#operations-refresh":
            class _Refresh:
                def count(self):
                    return 1 if page.present else 0

                @property
                def first(self):
                    return self

                def click(self):
                    if page.works and page.re_renders:
                        page.finder_value = ""  # the rebuild creates a fresh empty input
            return _Refresh()
        if selector == "#operations-run-finder":
            class _Finder:
                def count(self):
                    return 1

                @property
                def first(self):
                    return self

                def fill(self, value):
                    page.finder_value = value

                def input_value(self):
                    return page.finder_value
            return _Finder()
        raise AssertionError(f"unexpected selector {selector}")

    def expect_response(self, predicate, timeout=None):
        page = self

        class _Ctx:
            value = type("Response", (), {"status": 200})()

            def __enter__(self):
                if not page.works:
                    raise TimeoutError("no response")
                return self

            def __exit__(self, *exc):
                return False
        return _Ctx()

    def wait_for_timeout(self, ms):
        return None


def test_refresh_action_requires_the_control():
    from scripts.verify_control_room_rendering import _exercise_refresh_action

    results, errors = _exercise_refresh_action(_FakeRefreshPage(present=False), "dark")
    assert results == [] and any("missing" in e for e in errors)


def test_refresh_action_fails_on_an_inert_control():
    from scripts.verify_control_room_rendering import _exercise_refresh_action

    results, errors = _exercise_refresh_action(_FakeRefreshPage(works=False), "dark")
    assert results == [] and any("inert" in e for e in errors)


def test_refresh_action_fails_when_nothing_re_renders():
    from scripts.verify_control_room_rendering import _exercise_refresh_action

    results, errors = _exercise_refresh_action(_FakeRefreshPage(re_renders=False), "dark")
    assert results == [] and any("did not re-render" in e for e in errors)


def test_refresh_action_passes_on_a_working_control():
    from scripts.verify_control_room_rendering import _exercise_refresh_action

    results, errors = _exercise_refresh_action(_FakeRefreshPage(), "dark")
    assert errors == []
    assert [r["check"] for r in results] == ["governed-action-refresh"]


def test_site_gate_fails_a_vacuous_zero_svg_scan(tmp_path: Path):
    """The SITE gate must fail loud when its own extraction finds nothing to check.

    2026-09-22: four doubled regex escapes in the gate's raw ``PROBE`` string made every page
    yield zero SVGs and the gate reported PASS — the L24 run's browser evidence was therefore
    unproven, and the controller's acceptance could not distinguish "all diagrams render" from
    "nothing was checked". A vacuous scan is a FAIL, structurally (the Control Room gate's
    zero-captures rule, applied to the site)."""
    from apps.website.verify_svg_rendering import _write_report

    md, fails = _write_report(
        [],
        ["framework.html"],
        [(1440, 900)],
        tmp_path / "svg_render_report.md",
        tmp_path / "svg_render_report.json",
        "http://127.0.0.1:0",
    )
    joined = "\n".join(md)
    assert fails, "a zero-SVG scan must produce a failure row"
    assert any("ZERO diagrams" in str(row.get("fails")) for row in fails)
    assert "**FAIL**" in joined
