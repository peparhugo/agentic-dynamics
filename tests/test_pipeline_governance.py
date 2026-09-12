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

import json
import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src", _ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import pipeline as pl  # noqa: E402


class _FakeRedis:
    """The surface the matrix/review phases use (status hash + the fill's list lane)."""

    def __init__(self, statuses: dict | None = None) -> None:
        self.statuses = statuses or {}
        self.writes: list[tuple[str, dict]] = []
        self.lists: dict[str, list[str]] = {}

    def hgetall(self, key):
        return dict(self.statuses)

    def hset(self, key, mapping=None, **kwargs):
        self.writes.append((key, dict(mapping or {})))

    def llen(self, key):
        return len(self.lists.get(key, []))

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    def lrange(self, key, start, end):
        lst = self.lists.get(key, [])
        if end == -1:
            return list(lst[start:])
        return list(lst[start : end + 1])


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


# ── Wave B4: the matrix fill routes through the shared enqueue contract ─────


def _matrix_phase(**params):
    return pl.PlanPhase(
        id="m", kind="matrix",
        kind_params={"model": "test/model-b4", "workers": 4, **params},
    )


def _patch_fill_environment(monkeypatch, tmp_path, fake, enqueue):
    monkeypatch.setattr(pl, "_r", lambda: fake)
    monkeypatch.setattr(pl, "_get_state", lambda *a: pl.PlanState(status="pending"))
    monkeypatch.setattr(pl, "_workers_alive", lambda script: 1)
    monkeypatch.setattr(pl, "_spawn_workers", lambda *a, **k: None)
    monkeypatch.setattr(enqueue, "RESULTS_DIR", tmp_path)  # deterministic: nothing completed


def test_matrix_fill_routes_through_the_shared_enqueue_contract(monkeypatch, tmp_path):
    """The fill IS enqueue.py's contract: shared builder → queued-skip → admission → stamp →
    ONE push. The old code hand-rolled its own builder and raw-LPUSHed, bypassing admission."""
    import enqueue

    fake = _FakeRedis()
    _patch_fill_environment(monkeypatch, tmp_path, fake, enqueue)
    admitted = []
    real_admit = enqueue.admit_cells

    def spy_admit(cells, **kw):
        admitted.extend(c["cell_id"] for c in cells)
        return real_admit(cells, **kw)

    monkeypatch.setattr(enqueue, "admit_cells", spy_admit)

    assert pl._execute_matrix(_matrix_phase(), {"plan_name": "t"}) is False  # now running
    pushed = [json.loads(raw) for raw in fake.lists[enqueue.QUEUE_KEY]]
    assert len(pushed) == 30  # 3 stories × 2 tiers × (3 good + 2 bad)
    # admission saw exactly what was pushed (the list reads newest-first; lpush prepends)
    assert admitted == [c["cell_id"] for c in reversed(pushed)]
    assert all("enqueued_at" in c for c in pushed)  # transport stamps ride the shared fill
    seed_writes = [w for k, w in fake.writes if k == enqueue.STATUS_KEY]
    assert len(seed_writes) == 30  # story_status seeded through push_cells


def test_matrix_fill_refused_by_admission_pushes_nothing(monkeypatch, tmp_path, capsys):
    """An admission refusal fails the phase and pushes NOTHING — the queue never carries
    unbudgeted work (the bypass the old raw-LPUSH fill had)."""
    import enqueue

    fake = _FakeRedis()
    _patch_fill_environment(monkeypatch, tmp_path, fake, enqueue)

    def refuse(cells, **kw):
        raise enqueue.AdmissionDenied("budget exhausted")

    monkeypatch.setattr(enqueue, "admit_cells", refuse)

    assert pl._execute_matrix(_matrix_phase(), {"plan_name": "t"}) is False
    assert fake.lists.get(enqueue.QUEUE_KEY, []) == []
    assert "REFUSED" in capsys.readouterr().out
    assert fake.writes[-1][1].get("status") == "failed"


def test_matrix_fill_skips_cells_already_queued(monkeypatch, tmp_path):
    """A cell already waiting in the lane is not re-pushed — the shared queued-aware skip,
    which the old pipeline fill lacked entirely."""
    import enqueue

    fake = _FakeRedis()
    existing = {
        "cell_id": "model_b4_task_manager_api_tier1_minimal_good_clean",
        "story": "task_manager_api", "tier": "tier1_minimal", "quality": "good",
        "condition": "clean", "model": "test/model-b4",
    }
    fake.lpush(enqueue.QUEUE_KEY, json.dumps(existing))
    _patch_fill_environment(monkeypatch, tmp_path, fake, enqueue)

    pl._execute_matrix(_matrix_phase(), {"plan_name": "t"})
    pushed_ids = [json.loads(raw)["cell_id"] for raw in fake.lists[enqueue.QUEUE_KEY]]
    assert pushed_ids.count(existing["cell_id"]) == 1  # the pre-existing entry only
    assert len(pushed_ids) == 30  # 29 new + the pre-existing one


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
