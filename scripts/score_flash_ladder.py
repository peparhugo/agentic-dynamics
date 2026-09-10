#!/usr/bin/env python3
"""Score the flash-ladder portfolios from persisted ``run.py`` result files.

The ladder's production measurement path (g5 round-2 findings F2/F4): loads result JSON,
groups attempts by condition, EXCLUDES attempts with no collectable source
(``solution_code is None``) while reporting the excluded count, computes the pairwise
portfolio diversity per condition, and persists the score with input hashes + code sha.

    python3 scripts/score_flash_ladder.py experiments/results/flash_ladder/*.json \
        --group-by operator,strength --out experiments/results/flash_ladder/score.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.measurement.portfolio_score import score_result_files


def _expand_inputs(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        if any(ch in pattern for ch in "*?["):
            paths.extend(sorted(Path().glob(pattern)))
        else:
            paths.append(Path(pattern))
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("inputs", nargs="+", help="result JSON paths or glob patterns")
    parser.add_argument(
        "--out", default="", help="output path (default experiments/results/flash_ladder/…)"
    )
    parser.add_argument("--group-by", default="operator,strength")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args(argv)

    paths = _expand_inputs(args.inputs)
    if not paths:
        print("score_flash_ladder: no input files matched", file=sys.stderr)
        return 2

    group_by = tuple(field for field in args.group_by.split(",") if field)
    score = score_result_files(paths, group_by=group_by, threshold=args.threshold)
    payload = score.to_dict()

    if args.out:
        out = Path(args.out)
    else:
        stamp = score.generated_at.replace(":", "").replace("-", "")
        out = Path("experiments/results/flash_ladder") / f"flash_ladder_score_{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))

    for condition in payload["conditions"]:
        diversity = condition["diversity"]
        print(
            f"{condition['condition']}: n={condition['n_attempts']} "
            f"scored={condition['n_scored']} excluded_null={condition['excluded_null_source']} "
            f"coverage={diversity['coverage']} mean_composite={diversity['mean_composite']} "
            f"distinct_fraction={diversity['distinct_fraction']}"
        )
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
