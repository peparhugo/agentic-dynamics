"""scoreboard.py — the measured scoreboard command (``agentic-dynamics scoreboard``).

The s5a deliverable of the ``self_knowledge_layer`` wave (design
``docs/designs/proposed/self_knowledge_layer.md``): aggregates the s3 wave-verdict records into
the scoreboard's measured rows — waves completed, merge rate, adversarial-finding rate
(findings per reviewed wave), cost per wave (mean/median), time-to-merge, phases per wave, and
the per-model split — recomputed from the records, never hand-written totals. Aggregation lives
in :mod:`agentic_dynamics.knowledge.scoreboard`; this script owns argument parsing and the
human/machine report only.

    agentic-dynamics scoreboard                  # render the current measured scoreboard
    agentic-dynamics scoreboard --recompute      # re-aggregate the s3 records + rewrite it
    agentic-dynamics scoreboard --records-dir DIR # aggregate a specific records set (hermetic)

The durable document is written to ``experiments/results/scoreboard/scoreboard.json``
(``--out`` overrides) and is ONLY ever produced by a recompute — a stored total is a re-derived
total, never a hand-written one. ``--recompute`` forces the re-aggregation; without it the
command renders the stored document when one exists (an empty-but-valid document on an empty
record set is stored too, so "no waves yet" renders as that, never as an error) and recomputes
when none does. An explicitly named ``--records-dir`` always recomputes (a fixture/records set
cannot be "stale").

Exit codes: 0 on every completed render/recompute. 2 on a usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.knowledge import scoreboard as sb  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _display_path(path: Path) -> str:
    """Render a path for the human report: relative to the repo root when it lives under it."""
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())

#: The durable output the recompute writes (and the default render reads).
DEFAULT_OUT = ROOT / "experiments" / "results" / "scoreboard" / "scoreboard.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics scoreboard",
        description="The measured scoreboard: aggregate the s3 wave-verdict records into "
        "measured rows (waves, merge rate, adversarial findings, cost/wave, time-to-merge, "
        "phases/wave, per model) — recomputed from the records, never hand-written.",
    )
    parser.add_argument(
        "--recompute",
        action="store_true",
        help="re-aggregate the wave-verdict records and rewrite the durable scoreboard "
        "document (without it, a stored document is rendered when one exists)",
    )
    parser.add_argument(
        "--records-dir",
        default=None,
        help="directory of wave-verdict record artifacts to aggregate (default: the durable KB "
        "artifact dir). Naming one always recomputes.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help=f"where the recompute writes the durable scoreboard document (default: "
        f"{DEFAULT_OUT.relative_to(ROOT)})",
    )
    parser.add_argument(
        "--repository-id",
        default=sb.REPOSITORY_ID,
        help=f"repository identity the durable-record read filters on (default: "
        f"{sb.REPOSITORY_ID!r})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine scoreboard/v1 document on stdout (implies --dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="recompute and print the document, write nothing",
    )
    return parser


def _render_human(doc: dict[str, Any], *, source: str) -> str:
    """Render the scoreboard's measured rows as the human summary.

    Every figure shown is read from the document's ``body`` (the recomputed rows) — this
    renderer never recomputes or annotates totals of its own.
    """
    body = doc["body"]
    totals = body["totals"]
    cov = body["coverage"]
    lines = [
        f"[scoreboard] {totals['waves_completed']} wave(s) completed "
        f"({totals['waves_merged']} merged, merge rate "
        f"{totals['merge_rate'] if totals['merge_rate'] is not None else 'n/a'})",
        f"            adversarial: {totals['adversarial_findings_total']} finding(s) across "
        f"{totals['waves_reviewed']} reviewed wave(s), "
        f"{totals['adversarial_findings_per_reviewed_wave'] if totals['adversarial_findings_per_reviewed_wave'] is not None else 'n/a'} per reviewed wave",
        f"            cost/wave (mean {totals['cost_per_wave_usd']['mean']}, median "
        f"{totals['cost_per_wave_usd']['median']})  phases/wave (mean "
        f"{totals['phases_per_wave']['mean']}, median {totals['phases_per_wave']['median']})",
        f"            time-to-merge (mean "
        f"{totals['time_to_merge_hours']['mean']}, median "
        f"{totals['time_to_merge_hours']['median']}) over "
        f"{totals['time_to_merge_hours']['merged_with_timing']}/{cov['merged_waves']} merged "
        f"wave(s) with timing",
        f"            recomputed from {sb.EXTRACTOR_VERSION} records — {source}",
    ]
    for row in body["per_model"]:
        lines.append(
            f"  [{row['model']}] {row['waves']} wave(s), {row['merged']} merged "
            f"(rate {row['merge_rate']}), cost/wave mean {row['cost_per_wave_usd']['mean']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    records_dir = Path(args.records_dir).resolve() if args.records_dir else None
    out_path = Path(args.out).resolve() if args.out else DEFAULT_OUT

    recompute = bool(args.recompute) or records_dir is not None or args.json or args.dry_run
    document: dict[str, Any]
    source: str
    warnings: list[str]
    if not recompute and out_path.is_file():
        # Fast path: render the stored measured document (only ever written by a recompute).
        try:
            stored = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stored = None
        if isinstance(stored, dict) and stored.get("schema") == "scoreboard/v1":
            document = stored
            source = f"stored document {_display_path(out_path)}"
            warnings = []
        else:
            # No readable scoreboard/v1 document (absent, unreadable, or a foreign shape):
            # the measured answer is a fresh recompute, never a guessed render.
            document, warnings = sb.build_scoreboard(
                records_dir, repository_id=args.repository_id
            )
            source = "fresh recompute (no readable stored scoreboard/v1 document)"
            recompute = True
    else:
        document, warnings = sb.build_scoreboard(
            records_dir, repository_id=args.repository_id
        )
        source = (
            f"{records_dir if records_dir is not None else 'the durable KB artifact dir'}"
        )

    if recompute and not (args.json or args.dry_run):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    if args.json or args.dry_run:
        print(json.dumps(document, indent=2))
    else:
        print(_render_human(document, source=source))
        if recompute:
            print(f"[scoreboard] document written to {_display_path(out_path)}")
    for warning in warnings:
        print(f"[scoreboard] warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
