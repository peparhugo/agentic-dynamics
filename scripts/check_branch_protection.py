#!/usr/bin/env python3
"""Release-time branch-protection drift check for ``main`` (review P1).

Compares the LIVE GitHub branch-protection configuration against the committed,
documented expectation (``docs/release/branch_protection_settings.md`` — this
script's ``EXPECTED`` block is kept in lockstep with that doc) and fails on drift.

The live state is authoritative-by-observation only: GitHub allows pushes that
change protection outside this repo (the web UI, the API, another client), and a
committed doc cannot enforce anything by itself. This script is the scheduled /
release-time reconciliation: the operator (or a future CI job with admin-token
access) runs it and the repo refuses to call a release clean while it reports
drift.

Usage::

    python3 scripts/check_branch_protection.py            # compare + exit code
    python3 scripts/check_branch_protection.py --json     # dump the live config
    python3 scripts/check_branch_protection.py --repo owner/repo
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

#: The documented, intended configuration — keep in lockstep with
#: ``docs/release/branch_protection_settings.md``. These values describe the solo-dev
#: shape: required checks for non-admin contributors (admin override available, so the
#: operator's direct pushes are a privileged path with the CI gates as the safety net),
#: zero required reviews, and force-push/deletion disabled. Two-tier access is honest,
#: not accidental: ordinary contributors flow through PRs + checks; the experiment
#: runner/operator pushes directly with mandatory post-push checks and CI failure
#: visibility as the rollback signal.
EXPECTED = {
    "required_status_checks": {
        "strict": True,
        "contexts": ["lint", "test", "repro", "packaging"],
    },
    "required_pull_request_reviews": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews": True,
    },
    "enforce_admins": False,
    "required_linear_history": False,
    "allow_force_pushes": False,
    "allow_deletions": False,
    "required_conversation_resolution": False,
    "required_signatures": False,
}


def _gh(args: list[str]) -> dict:
    """Run ``gh api ...`` and return the parsed JSON; exit loudly on any problem."""
    try:
        out = subprocess.run(
            ["gh", "api", *args], capture_output=True, text=True, timeout=60
        )
    except FileNotFoundError:
        sys.exit("check_branch_protection: 'gh' not found — install the GitHub CLI")
    if out.returncode != 0:
        sys.exit(f"check_branch_protection: gh api failed: {out.stderr.strip()}")
    return json.loads(out.stdout)


def resolve_repo(repo: str | None) -> str:
    """Resolve ``owner/repo`` from ``--repo``, else the current gh identity's repo."""
    if repo:
        return repo
    try:
        out = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError:
        sys.exit("check_branch_protection: 'gh' not found — install the GitHub CLI")
    if out.returncode != 0:
        sys.exit(
            "check_branch_protection: could not resolve the repository — pass --repo owner/repo"
        )
    return out.stdout.strip()


def compare_live(live: dict) -> list[str]:
    """Return the drift messages ([] = the live config matches EXPECTED exactly).

    Pure function — testable without a live GitHub session. Expected keys missing
    from the live config, and expected values differing from the live values, each
    produce one message.
    """
    drifts: list[str] = []
    for key, expected in EXPECTED.items():
        live_value = live.get(key)
        if live_value is None:
            drifts.append(f"{key}: absent from the live config (expected {expected!r})")
            continue
        if isinstance(expected, dict):
            for sub_key, sub_expected in expected.items():
                sub_live = live_value.get(sub_key)
                if sub_live != sub_expected:
                    drifts.append(
                        f"{key}.{sub_key}: live {sub_live!r} != expected {sub_expected!r}"
                    )
            continue
        # GitHub returns the boolean settings wrapped as {"enabled": bool} — unwrap
        # before comparing so the expectation stays the plain intended value.
        if isinstance(live_value, dict) and "enabled" in live_value:
            live_value = live_value["enabled"]
        if live_value != expected:
            drifts.append(f"{key}: live {live_value!r} != expected {expected!r}")
    return drifts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", default=None, help="owner/repo to check (default: the current repo)"
    )
    parser.add_argument(
        "--branch", default="main", help="branch to check (default: main)"
    )
    parser.add_argument(
        "--json", action="store_true", help="print the live protection config and exit"
    )
    args = parser.parse_args()

    repo = resolve_repo(args.repo)
    live = _gh([f"repos/{repo}/branches/{args.branch}/protection"])
    if args.json:
        print(json.dumps(live, indent=2, sort_keys=True))
        return 0

    drifts = compare_live(live)
    print(f"branch protection — {repo} #{args.branch}")
    for key, expected in EXPECTED.items():
        live_value = live.get(key)
        if isinstance(expected, dict):
            for sub_key, sub_expected in expected.items():
                ok = live_value is not None and live_value.get(sub_key) == sub_expected
                print(
                    f"  [{'ok' if ok else 'MISMATCH'}] {key}.{sub_key}: "
                    f"live {live_value.get(sub_key) if live_value else None!r} "
                    f"expected {sub_expected!r}"
                )
        else:
            if isinstance(live_value, dict) and "enabled" in live_value:
                live_value = live_value["enabled"]
            ok = live_value == expected
            print(
                f"  [{'ok' if ok else 'MISMATCH'}] {key}: "
                f"live {live_value!r} expected {expected!r}"
            )
    if drifts:
        print(
            f"\nDRIFT — {len(drifts)} setting(s) disagree with "
            f"docs/release/branch_protection_settings.md; fix the live config or "
            f"update the doc, then re-run"
        )
        return 1
    print("\nclean — the live protection matches the committed settings doc")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
