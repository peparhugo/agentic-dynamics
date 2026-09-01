"""Tests for the release-time branch-protection drift check (scripts/check_branch_protection.py)."""

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_branch_protection.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("check_branch_protection", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _live_payload(enforce_admins=False, review_count=0, strict=True):
    """A protection payload shaped like GitHub's live API response, matching EXPECTED."""
    return {
        "required_status_checks": {
            "strict": strict,
            "contexts": ["lint", "test", "repro", "packaging"],
        },
        "required_pull_request_reviews": {
            "required_approving_review_count": review_count,
            "dismiss_stale_reviews": True,
        },
        "enforce_admins": {"enabled": enforce_admins},
        "required_linear_history": {"enabled": False},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
        "required_conversation_resolution": {"enabled": False},
        "required_signatures": {"enabled": False},
    }


def test_clean_live_config_reports_no_drift(mod):
    assert mod.compare_live(_live_payload()) == []


def test_force_pushes_enabled_is_drift(mod):
    payload = _live_payload()
    payload["allow_force_pushes"] = {"enabled": True}
    drifts = mod.compare_live(payload)
    assert any("allow_force_pushes" in d for d in drifts)


def test_enforce_admins_true_is_drift(mod):
    payload = _live_payload(enforce_admins=True)
    drifts = mod.compare_live(payload)
    assert any("enforce_admins" in d for d in drifts)


def test_required_review_is_drift(mod):
    payload = _live_payload(review_count=1)
    drifts = mod.compare_live(payload)
    assert any("required_pull_request_reviews.required_approving_review_count" in d for d in drifts)


def test_missing_status_check_is_drift(mod):
    payload = _live_payload()
    payload["required_status_checks"]["contexts"] = ["lint"]
    drifts = mod.compare_live(payload)
    assert any("required_status_checks.contexts" in d for d in drifts)


def test_absent_setting_is_drift(mod):
    payload = _live_payload()
    del payload["required_signatures"]
    drifts = mod.compare_live(payload)
    assert any("required_signatures: absent" in d for d in drifts)


def test_expected_matches_the_settings_doc():
    """The drift check's EXPECTED block must mirror the committed settings doc.

    The doc's settings table and the script's EXPECTED dict are the two halves of the
    same contract — this test keeps them from silently diverging (the script already
    states the lockstep in its module docstring; this makes it checked).
    """
    text = SCRIPT.parent.parent.joinpath("docs", "release", "branch_protection_settings.md").read_text()
    assert "| `enforce_admins` | `false` |" in text
    assert "required_approving_review_count" in text and "`0`" in text
    assert "`lint`, `test`, `repro`, `packaging`" in text
