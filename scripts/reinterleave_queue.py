"""Re-interleave the story queue round-robin across providers (CLI).

Thin wrapper over :mod:`instrument.queue_reinterleave` — the core logic lives
there so this CLI and the Control Room's ``POST /api/queue/reinterleave``
endpoint can never drift.

Usage:
    python scripts/reinterleave_queue.py            # reorder in place
    python scripts/reinterleave_queue.py --dry-run  # preview without writing
    python scripts/reinterleave_queue.py --json     # machine-readable report
"""

import json
import sys

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.control.queue_reinterleave import (  # noqa: E402
    connect,
    provider_summary,
    read_queue,
    reinterleave_cells,
    write_queue,
)


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    json_out = "--json" in sys.argv

    r = connect()
    before = read_queue(r)
    reordered = reinterleave_cells(before)

    if not dry_run:
        write_queue(r, reordered)

    before_summary = provider_summary(before)
    after_summary = provider_summary(reordered)

    report = {
        "count": len(before),
        "before_longest_provider_run": before_summary["longest_provider_run"],
        "after_longest_provider_run": after_summary["longest_provider_run"],
        "before_by_provider": before_summary["by_provider"],
        "after_by_provider": after_summary["by_provider"],
        "after_provider_order": after_summary["order"],
        "dry_run": dry_run,
    }

    if json_out:
        print(json.dumps(report, indent=2))
        return

    action = "dry-run, nothing written" if dry_run else "written to queue"
    print(f"Reinterleaved {report['count']} jobs ({action})")
    print(f"  longest same-provider run: "
          f"{report['before_longest_provider_run']} -> {report['after_longest_provider_run']}")
    print(f"  before: {report['before_by_provider']}")
    print(f"  after:  {report['after_by_provider']}")
    order = report["after_provider_order"]
    print(f"  order:  {' '.join(order[:20])}{' ...' if len(order) > 20 else ''}")


if __name__ == "__main__":
    main()
