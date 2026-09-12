"""Wave A5 — the pipeline proposes, the governed commands dispose.

The review's #1 reproductions, pinned:

* ``kind: ship`` and ``kind: pr_merge`` can no longer merge/push anything: both executors
  REFUSE with guidance (they remain registered so old plan references fail closed), and the
  shipped plans no longer name them;
* the matrix phase completes on ITS OWN cells only — an unrelated row's completion in the
  shared status hash no longer marks the phase done while its own job runs;
* the review phase honors the subprocess's exit code (exit 17 previously wrote ``done``).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src", _ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import pipeline as pl  # noqa: E402


class _FakeRedis:
    """hgetall/hset only — the surface the matrix/review phases use."""

    def __init__(self, statuses: dict | None = None) -> None:
        self.statuses = statuses or {}
        self.writes: list[tuple[str, dict]] = []

    def hgetall(self, key):
        return dict(self.statuses)

    def hset(self, key, mapping=None, **kwargs):
        self.writes.append((key, dict(mapping or {})))

    def llen(self, key):
        return 0

    def lpush(self, key, value):
        return 1


def _phase(kind: str, **params):
    return pl.PlanPhase(id="p", kind=kind, kind_params=params)


def test_ship_refuses_with_governed_path_guidance(capsys):
    assert pl._execute_ship(_phase("ship"), {}) is False
    out = capsys.readouterr().out
    assert "REFUSED" in out and "workflow promote" in out


def test_pr_merge_refuses_with_governed_path_guidance(capsys):
    assert pl._execute_pr_merge(_phase("pr_merge"), {}) is False
    out = capsys.readouterr().out
    assert "REFUSED" in out and "controller" in out


def test_shipped_plans_no_longer_name_permanence_phases():
    plans = pl.load_plans(_ROOT / "experiments" / "definitions" / "configs" / "plans.yaml")
    for name, plan in plans.items():
        kinds = {p.kind for p in plan.phases}
        assert not (kinds & {"ship", "pr_merge"}), f"{name} still names a permanence phase"
    assert [p.id for p in plans["feature"].phases][-1] == "review"
    assert [p.id for p in plans["ship_features"].phases][-1] == "prs"


def test_matrix_completes_on_its_own_cells_not_unrelated_rows(monkeypatch):
    """The reproduction: own job running, unrelated job done — the phase must NOT finish."""
    fake = _FakeRedis(statuses={"own-1": "running", "unrelated": "done"})
    monkeypatch.setattr(pl, "_r", lambda: fake)
    monkeypatch.setattr(
        pl, "_get_state",
        lambda plan_name, phase_id: pl.PlanState(
            status="running", jobs_total=1, jobs_ids=["own-1"],
        ),
    )
    monkeypatch.setattr(pl, "_workers_alive", lambda script: 1)
    monkeypatch.setattr(pl, "_spawn_workers", lambda *a, **k: None)

    assert pl._execute_matrix(_phase("matrix", workers=4), {"plan_name": "t"}) is False
    # progress recorded honestly (0 of its own done), and no done state written
    assert all(w[1].get("status") != "done" for w in fake.writes)

    # its own cell completes -> the phase completes
    fake.statuses["own-1"] = "done"
    assert pl._execute_matrix(_phase("matrix", workers=4), {"plan_name": "t"}) is True


def test_review_phase_honors_the_subprocess_exit_code(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(pl, "_r", lambda: fake)
    monkeypatch.setattr(pl, "_get_state", lambda *a: pl.PlanState(status="running"))
    monkeypatch.setattr(
        pl.subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=17),
    )
    assert pl._execute_review(_phase("review"), {"plan_name": "t"}) is False
    assert fake.writes and fake.writes[-1][1].get("status") == "failed"

    monkeypatch.setattr(pl.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0))
    assert pl._execute_review(_phase("review"), {"plan_name": "t"}) is True
    assert fake.writes[-1][1].get("status") == "done"
