"""Tests for reinterleave_queue.py — round-robin provider interleave."""

import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from reinterleave_queue import reinterleave_cells  # noqa: E402


def _cell(provider: str, idx: int) -> dict:
    """Build a job cell with a provider-scoped model id."""
    return {
        "cell_id": f"{provider}_job_{idx}",
        "model": f"{provider}/model-{idx}",
        "story": "task_manager_api",
    }


def test_empty_input_is_identity() -> None:
    """An empty queue passes through unchanged (no crash, no jobs created)."""
    assert reinterleave_cells([]) == []


def test_single_job_preserved() -> None:
    """A single job survives the reorder with its provider intact."""
    jobs = [_cell("openai", 0)]
    assert reinterleave_cells(jobs) == jobs


def test_consecutive_providers_always_differ() -> None:
    """For any adjacent pair in the output, providers must differ.

    The core guarantee of the reinterleave: workers must never pick two jobs
    from the same provider back to back, otherwise they hammer one provider.
    """
    jobs: list[dict] = []
    for i in range(40):
        jobs.append(_cell(["anthropic", "openai", "deepseek"][i % 3], i))

    out = reinterleave_cells(jobs)

    providers = [c["model"].split("/", 1)[0] for c in out]
    for a, b in zip(providers, providers[1:]):
        assert a != b, f"adjacent same-provider run: {a} at {providers.index(a)}"


def test_imbalanced_still_never_adjacent() -> None:
    """A heavily imbalanced queue still yields no adjacent same-provider pair.

    50 openai + 25 anthropic + 1 deepseek = 76 jobs. The openai majority is
    large (50 > 38), so a *perfect* interleave is infeasible — the function
    must raise rather than emit adjacent same-provider cells.
    """
    jobs = [_cell("openai", i) for i in range(50)]
    jobs += [_cell("anthropic", i) for i in range(25)]
    jobs += [_cell("deepseek", 0)]

    with pytest.raises(ValueError, match="Reinterleave impossible"):
        reinterleave_cells(jobs)


def test_job_preservation_no_loss_or_duplication() -> None:
    """Every job appears exactly once — nothing lost, nothing duplicated."""
    jobs: list[dict] = []
    for i in range(57):
        jobs.append(_cell(["anthropic", "openai", "deepseek"][i % 3], i))

    out = reinterleave_cells(jobs)

    assert len(out) == len(jobs), "job count changed"
    # Same multiset of cell ids (order-independent) => no loss or duplication.
    assert Counter(c["cell_id"] for c in out) == Counter(c["cell_id"] for c in jobs)
    # Same multiset of full job objects as well.
    assert Counter(json_id(c) for c in out) == Counter(json_id(c) for c in jobs)


def json_id(cell: dict) -> str:
    """Canonical string key for a job cell."""
    return repr(sorted(cell.items()))


def test_provider_groups_preserve_relative_order() -> None:
    """Jobs from the same provider keep their original relative order."""
    jobs = [_cell("anthropic", i) for i in range(10)] + [_cell("openai", i) for i in range(10)]

    out = reinterleave_cells(jobs)

    anthropic_ids = [c["cell_id"] for c in out if c["model"].startswith("anthropic")]
    assert anthropic_ids == [f"anthropic_job_{i}" for i in range(10)]
