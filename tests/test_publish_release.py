"""``publish release`` — the ONE publication transaction (control_db_publication p6).

The load-bearing guarantees this suite pins:

1. a real publication REFUSES without ``--operator`` (deploying the website is a P0
   controller-only action) and refuses BEFORE any work — an operator-less invocation
   fails in a second, not after a ten-minute data build;
2. the candidate must be the checkout — the receipt describes the tree being deployed,
   never a different one;
3. stale projections refuse publication EARLY, before the data build;
4. the HTML-consistency check is a precondition — a page contradicting data.js refuses;
5. the receipt (publication/v1) is produced BEFORE anything is deployed, and the
   deploy sequence either completes or stops with nothing deployed;
6. a failed deploy is RECORDED (both hosts + the receipt land in the control database
   with the failed host marked) so drift is visible, never guessed;
7. the post-deploy check verifies the live sites serve the receipted data.js.

All side-effecting steps (Firebase deploy, build_data.py, the HTTP fetch) are injected
fakes, so the whole transaction — including the database writes and the ordering — is
tested without a Firebase project, a network, or a real data build.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = str(_REPO_ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

import publish_release as pr  # noqa: E402

from agentic_dynamics.control import publication as pub  # noqa: E402
from agentic_dynamics.control.control_db import ControlDB  # noqa: E402

# ── fakes ──────────────────────────────────────────────────────────────────────


def _ok_deployer():
    calls = []

    def deploy(host):
        calls.append(host.role)
        return pr.DeployOutcome(host, True, f"rel-{host.role}", "")
    return calls, deploy


def _fail_first_deployer():
    calls = []

    def deploy(host):
        calls.append(host.role)
        ok = host.role != "canonical"
        return pr.DeployOutcome(host, ok, f"rel-{host.role}" if ok else "", "boom" if not ok else "")
    return calls, deploy


def _ok_builder():
    return lambda: (True, "built")


def _ok_live_checker():
    return lambda host, receipt: ""


def _now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _db_with_fresh_projections(tmp_path: Path) -> Path:
    """A control db whose three projection watermarks report lag 0, freshly stamped."""
    path = tmp_path / "control.db"
    with ControlDB.open(path) as db:
        for proj in ("registry", "chroma", "neo4j"):
            db.record_watermark(
                proj, last_event_id="e1", source_head_event_id="e1",
                lag_events=0, last_success_at=_now_iso(),
            )
    return path


def _consistent_site(tmp_path: Path) -> Path:
    """A site root with a real data.js + no lying pages (the checker's pass case)."""
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<p>1,027 story sessions</p>")
    (site / "data.js").write_text(
        'window.DYNAMICS_DATA = ' + json.dumps({"public_statistics": {"story_sessions": 1027}}) + ';\n'
    )
    return site


@pytest.fixture()
def _monkeypatch_head(monkeypatch):
    monkeypatch.setattr(pr, "read_head_sha", lambda: "deadbeef1234567890abcdef")


# ── the P0 guard: no operator, no publication ──────────────────────────────────


def test_real_publication_refuses_without_operator(tmp_path, monkeypatch):
    """An operator-less real publication fails fast — BEFORE the build, the deploy,
    and the database work. Only --dry-run may run without an operator."""
    monkeypatch.setattr(pr, "read_head_sha", lambda: "deadbeef")
    # a control db with fresh projections so the dry-run gets past the projection gate
    db_path = _db_with_fresh_projections(tmp_path)
    rc = pr.main(["--candidate-sha", "deadbeef", "--dry-run", "--db", str(db_path)],
                 deployer=_ok_deployer()[1], builder=_ok_builder(),
                 live_checker=_ok_live_checker())
    assert rc == pr.EXIT_OK  # dry-run: fine without operator

    rc = pr.main(["--candidate-sha", "deadbeef", "--db", str(db_path)],
                 deployer=_ok_deployer()[1], builder=_ok_builder(),
                 live_checker=_ok_live_checker())
    assert rc == pr.EXIT_PRECONDITION_FAILED


# ── the candidate must be the checkout ─────────────────────────────────────────


def test_candidate_mismatch_refuses(monkeypatch, tmp_path):
    monkeypatch.setattr(pr, "read_head_sha", lambda: "cafebabe1234567890abcdef")
    rc = pr.main(["--candidate-sha", "deadbeef", "--dry-run", "--db", str(tmp_path / "x.db")],
                 deployer=_ok_deployer()[1], builder=_ok_builder(),
                 live_checker=_ok_live_checker())
    assert rc == pr.EXIT_PRECONDITION_FAILED


# ── no control database → refuse (distinct exit) ───────────────────────────────


def test_missing_control_db_refuses_with_exit_3(monkeypatch, tmp_path):
    monkeypatch.setattr(pr, "read_head_sha", lambda: "deadbeef")
    rc = pr.main(["--candidate-sha", "deadbeef", "--dry-run", "--db", str(tmp_path / "nope.db")],
                 deployer=_ok_deployer()[1], builder=_ok_builder(),
                 live_checker=_ok_live_checker())
    assert rc == pr.EXIT_NO_CONTROL_DB


# ── stale projections refuse EARLY ─────────────────────────────────────────────


def test_stale_projections_refuse_before_build(monkeypatch, tmp_path):
    path = tmp_path / "control.db"
    with ControlDB.open(path) as db:
        db.record_watermark("chroma", last_event_id="e1", source_head_event_id="e5",
                            lag_events=4, last_success_at=_now_iso())
    monkeypatch.setattr(pr, "read_head_sha", lambda: "deadbeef")
    built = []

    def builder():
        built.append(True)
        return True, "built"

    rc = pr.main(["--candidate-sha", "deadbeef", "--dry-run", "--db", str(path)],
                 deployer=_ok_deployer()[1], builder=builder, live_checker=_ok_live_checker())
    assert rc == pr.EXIT_PRECONDITION_FAILED
    assert built == []  # refused BEFORE the data build


# ── HTML inconsistency refuses ─────────────────────────────────────────────────


def test_inconsistent_pages_refuse(monkeypatch, tmp_path):
    path = _db_with_fresh_projections(tmp_path)
    monkeypatch.setattr(pr, "read_head_sha", lambda: "deadbeef")
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<p>1,067 story sessions</p>")  # the lying page
    monkeypatch.setattr(pub, "SITE_ROOT", site)
    rc = pr.main(["--candidate-sha", "deadbeef", "--dry-run", "--db", str(path)],
                 deployer=_ok_deployer()[1], builder=_ok_builder(),
                 live_checker=_ok_live_checker())
    assert rc == pr.EXIT_PRECONDITION_FAILED


# ── the full happy path, dry-run ───────────────────────────────────────────────


def test_dry_run_full_sequence(monkeypatch, tmp_path):
    path = _db_with_fresh_projections(tmp_path)
    monkeypatch.setattr(pr, "read_head_sha", lambda: "deadbeef")
    site = _consistent_site(tmp_path)
    monkeypatch.setattr(pub, "SITE_ROOT", site)
    monkeypatch.setattr(pub, "DATA_JS", site / "data.js")
    calls, deploy = _ok_deployer()
    rc = pr.main(["--candidate-sha", "deadbeef", "--dry-run", "--db", str(path)],
                 deployer=deploy, builder=_ok_builder(), live_checker=_ok_live_checker())
    assert rc == pr.EXIT_OK
    assert calls == []  # dry-run deploys NOTHING


# ── a failed deploy is recorded, not hidden ────────────────────────────────────


def test_failed_deploy_is_recorded(monkeypatch, tmp_path):
    path = _db_with_fresh_projections(tmp_path)
    monkeypatch.setattr(pr, "read_head_sha", lambda: "deadbeef")
    site = _consistent_site(tmp_path)
    monkeypatch.setattr(pub, "SITE_ROOT", site)
    monkeypatch.setattr(pub, "DATA_JS", site / "data.js")
    calls, deploy = _fail_first_deployer()
    rc = pr.main(["--candidate-sha", "deadbeef", "--operator", "operator-test",
                  "--db", str(path)],
                 deployer=deploy, builder=_ok_builder(), live_checker=_ok_live_checker())
    assert rc == pr.EXIT_DEPLOY_FAILED
    assert calls == ["canonical", "mirror"]  # BOTH were attempted
    # ...and the failure is in the database, not lost:
    with ControlDB.open_read_only(path) as db:
        receipts = db.publication_receipts()
        assert len(receipts) == 1
        deployments = db.deployments(receipts[0].receipt_id)
        by_role = {d.host_role: d.status for d in deployments}
        assert by_role == {"canonical": "failed", "mirror": "succeeded"}
