"""lab_beta_from_corpus unit tests — pure functions only, no DB, no fitting on real data."""

from datetime import datetime, timezone

from scripts.lab_beta_from_corpus import LADDER_WINDOW, _bin_of, _excluded, _fit_ols


import pytest
pytestmark = pytest.mark.fast

def _row(**kw):
    base = {
        "duration_s": 120.0,
        "tokens": 5000,
        "tokens_input": 1000,
        "cache_read": 0,
        "cost_usd": 0.1,
        "start": LADDER_WINDOW[1],
        "end": LADDER_WINDOW[1],
    }
    base.update(kw)
    return base


def test_ols_exact_line():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    ys = [2.0 * x + 1.0 for x in xs]
    fit = _fit_ols(xs, ys)
    assert fit["slope"] == 2.0
    assert fit["beta"] == -2.0
    assert fit["r2"] == 1.0
    assert fit["n"] == 6


def test_ols_insufficient_n():
    fit = _fit_ols([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert fit["beta"] is None


def test_ols_flat_data_has_zero_beta():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [3.0] * 5
    fit = _fit_ols(xs, ys)
    assert abs(fit["beta"]) < 1e-9


def test_noise_exclusion():
    assert _excluded(_row(duration_s=5.0, tokens=5000))
    assert _excluded(_row(duration_s=120.0, tokens=50))
    assert not _excluded(_row(duration_s=120.0, tokens=5000))


def test_ladder_window_exclusion():
    inside = _row(
        start=datetime(2026, 8, 30, 22, 0, tzinfo=timezone.utc),
        end=datetime(2026, 8, 30, 23, 0, tzinfo=timezone.utc),
    )
    assert _excluded(inside)
    before = _row(
        start=datetime(2026, 8, 30, 20, 0, tzinfo=timezone.utc),
        end=datetime(2026, 8, 30, 21, 0, tzinfo=timezone.utc),
    )
    assert not _excluded(before)


def test_bin_edges():
    assert _bin_of(1.0) == "1"
    assert _bin_of(2.5) == "2-3"
    assert _bin_of(4.9) == "4-5"
    assert _bin_of(7.0) == "6-8"
    assert _bin_of(12.0) == "9+"
    assert _bin_of(100.0) == "9+"
