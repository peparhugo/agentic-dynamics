#!/usr/bin/env python3
"""Publication as ONE transaction (``control_db_publication`` p6).

    agentic-dynamics publish release --candidate-sha <sha> --dry-run
    agentic-dynamics publish release --candidate-sha <sha> --operator <name>

The command that replaces "run ``build_data.py``, eyeball the site, then type two ``firebase
deploy`` lines and hope you remembered the second one". Every step below is a precondition for
the next, and the whole sequence either completes or stops with nothing deployed:

.. code-block:: text

    1. verify the candidate sha       — the tree being published is the tree that was verified
    2. verify projections             — p3 watermarks: registry/chroma/neo4j fresh enough
    3. build data                     — scripts/build_data.py regenerates apps/website/data.js
    4. verify HTML consistency        — every page's numbers agree with data.js
    5. RECEIPT (publication/v1)       — the join point; produced before anything is deployed
    6. deploy canonical + mirror      — BOTH Firebase hosts, from apps/website/
    7. record                         — receipt + one row per host in the control database
    8. post-deploy check              — the live sites serve the data.js the receipt names

This file is the *shell*, in the split the control plane uses everywhere: the derivations,
schemas, and checks live in :mod:`agentic_dynamics.control.publication`, which pytest imports
directly. What lives here is exactly the impure part — running subprocesses, talking to
Firebase, writing to the database, printing, and choosing exit codes.

Authority. Deploying the website is a **P0** action: the controller alone (``AGENTS.md``). This
command therefore refuses to deploy without ``--operator``, and records that name on the receipt.
``--dry-run`` needs no operator because it deploys nothing — it prints the plan and stops before
step 6. An agent may run ``--dry-run``; only the controller runs the real thing.

Exit codes — so a caller can branch without parsing output:

* ``0`` — published (or, under ``--dry-run``, the plan is clean and would publish).
* ``1`` — a precondition failed: stale projections, a page that contradicts data.js, an invalid
  receipt, or a build that did not produce the artifacts. Nothing was deployed.
* ``2`` — a deploy failed. Partial state is possible and is RECORDED: the receipt and both host
  rows are in the database, with the failed host marked ``failed``, so the next operator can see
  which host is behind rather than having to guess.
* ``3`` — there is no control database. Distinct from an empty one, deliberately, and the same
  code ``control status`` uses for the same condition.
* ``4`` — the post-deploy check failed. The deploys happened and are recorded; what could not be
  confirmed is that the live sites serve what the receipt says.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: F401  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: F401


from agentic_dynamics.control import publication as pub  # noqa: E402
from agentic_dynamics.control.control_db import ControlDB, ControlDBError  # noqa: E402

#: See the module docstring for what each code means.
EXIT_OK = 0
EXIT_PRECONDITION_FAILED = 1
EXIT_DEPLOY_FAILED = 2
EXIT_NO_CONTROL_DB = 3
EXIT_POST_DEPLOY_FAILED = 4


# ── Deployment ───────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DeployOutcome:
    """The result of deploying one host — the shape the control database records."""

    host: pub.FirebaseHost
    ok: bool
    #: The provider's deployment identifier, when it could be parsed from the output.
    release_id: str
    #: Trimmed command output, kept as the ``detail`` column so a failure is diagnosable later.
    detail: str


#: Firebase Hosting prints its release identity in a couple of shapes depending on version.
#: Both are tried; failing to parse an id is NOT a deploy failure (the deploy plainly succeeded),
#: it just means the recorded ``release_id`` is empty — which the row says honestly rather than
#: filling in a plausible-looking value.
_RELEASE_ID_PATTERNS = (
    re.compile(r"Hosting URL:\s*(?P<url>\S+)"),
    re.compile(r"release[\s_-]?(?:id|name)[\"':\s]+(?P<id>[\w./-]+)", re.IGNORECASE),
    re.compile(r"sites/[\w-]+/versions/(?P<id>[\w-]+)"),
)


def parse_release_id(output: str) -> str:
    """Best-effort extraction of a deployment identifier from ``firebase deploy`` output.

    Returns ``""`` when nothing matches. Deliberately not an error: the identifier is evidence
    that makes a deployment checkable against the provider, and its absence should be visible in
    the record rather than papered over with a guess.
    """
    for pattern in _RELEASE_ID_PATTERNS:
        match = pattern.search(output)
        if match:
            return match.groupdict().get("id") or match.groupdict().get("url") or ""
    return ""


def firebase_deploy(host: pub.FirebaseHost, *, site_root: Path, timeout: int = 900) -> DeployOutcome:
    """Deploy one host with the Firebase CLI, from the site root.

    The command is exactly the pair documented in ``AGENTS.md`` — ``firebase deploy --only
    hosting`` for the canonical project and the same with ``--project`` for the mirror — run from
    ``apps/website/`` because that is where ``firebase.json`` lives (with ``public: "."``).
    Encoding it here is the point of p6: the operator no longer has to remember to run it twice.
    """
    cmd = ["firebase", "deploy", "--only", "hosting"]
    if host.role != "canonical":
        cmd += ["--project", host.project]
    try:
        completed = subprocess.run(
            cmd, cwd=site_root, capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError:
        return DeployOutcome(host, False, "", "firebase CLI not found on PATH")
    except subprocess.TimeoutExpired:
        return DeployOutcome(host, False, "", f"firebase deploy timed out after {timeout}s")
    output = (completed.stdout or "") + (completed.stderr or "")
    return DeployOutcome(
        host=host,
        ok=completed.returncode == 0,
        release_id=parse_release_id(output),
        detail=output.strip()[-2000:],
    )


def check_live_site(host: pub.FirebaseHost, receipt: dict[str, Any], *, timeout: int = 30) -> str:
    """Post-deploy check: does the live host serve the ``data.js`` this receipt names?

    Returns ``""`` on success or a human-readable problem. Compares the SHA-256 of the fetched
    ``data.js`` against ``data_js_sha256`` — which is the only check that actually closes the
    loop. "The deploy command exited 0" says the upload was accepted; this says the bytes a
    visitor receives are the bytes that were verified.

    Network access is not assumed: an unreachable host is reported as a problem the operator can
    act on (or skip with ``--no-post-deploy-check``), never silently treated as a pass.
    """
    import hashlib
    import urllib.error
    import urllib.request

    url = host.url.rstrip("/") + "/data.js"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - fixed https
            body = response.read()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return f"{host.role} ({url}): unreachable — {exc}"
    digest = hashlib.sha256(body).hexdigest()
    expected = receipt.get("data_js_sha256", "")
    if expected and digest != expected:
        return (
            f"{host.role} ({url}): serves data.js sha256 {digest[:12]}…, "
            f"receipt says {expected[:12]}… — the live site is not this release"
        )
    return ""


# ── The transaction ──────────────────────────────────────────────────────────────────────────


def run_build_data(*, python: str = sys.executable, timeout: int = 3600) -> tuple[bool, str]:
    """Regenerate ``apps/website/data.js`` by running the maintained build script.

    A subprocess rather than an import: ``build_data.py`` is a script with module-level state and
    its own argument parsing, and the CLI's standing rule is that it *composes* scripts and never
    re-implements them.
    """
    completed = subprocess.run(
        [python, str(ROOT / "scripts" / "build_data.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode == 0, output.strip()[-4000:]


def read_head_sha() -> str:
    """The checked-out HEAD sha, or ``""`` outside a git checkout."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
        )
    except FileNotFoundError:  # pragma: no cover - git is present wherever this runs
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def verify_candidate_sha(candidate: str, *, head: str) -> str:
    """Confirm the working tree IS the candidate. Returns ``""`` or a problem description.

    The receipt claims a tree; if the checkout is on a different commit, the receipt would
    describe one tree while the deploy shipped another — the precise class of untraceable
    publication this command exists to end. Abbreviated shas are accepted (a prefix match) since
    that is how operators type them.
    """
    if not candidate:
        return "no --candidate-sha given"
    if not head:
        return "cannot determine HEAD (not a git checkout?)"
    if not (head.startswith(candidate) or candidate.startswith(head)):
        return (
            f"--candidate-sha {candidate} does not match HEAD {head[:12]} — check out the "
            "candidate before publishing, so the receipt describes the tree being deployed"
        )
    return ""


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface."""
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics publish release",
        description="Publish the website as ONE verified transaction (publication/v1 receipt).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Deploying is a P0 action (the controller alone): a real publication requires "
            "--operator. Use --dry-run to print the plan without deploying anything."
        ),
    )
    parser.add_argument(
        "--candidate-sha",
        required=True,
        help="The exact tree to publish. Must match HEAD (a prefix is fine).",
    )
    parser.add_argument(
        "--operator",
        default="",
        help="Who is publishing. Required for a real deploy; recorded on the receipt.",
    )
    parser.add_argument(
        "--run-id", default="", help="Control-db run that produced the candidate, if any."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run every verification and print the full plan, then stop before deploying.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Do not run build_data.py; verify the data.js already present.",
    )
    parser.add_argument(
        "--max-lag",
        type=int,
        default=0,
        help="Projection lag tolerated, in events (default 0 — strict). Recorded on the receipt.",
    )
    parser.add_argument(
        "--allow-unreported-projections",
        action="store_true",
        help=(
            "Publish even when a projection has never reported. For a checkout that has genuinely "
            "never run a projector; recorded on the receipt so a relaxed gate stays visible."
        ),
    )
    parser.add_argument(
        "--no-post-deploy-check",
        action="store_true",
        help="Skip fetching the live sites after deploying (offline operator).",
    )
    parser.add_argument("--db", default=None, help="Control database path (default: resolved).")
    parser.add_argument("--json", action="store_true", help="Emit the receipt as JSON on stdout.")
    return parser


def _emit(message: str, *, quiet: bool) -> None:
    """Print progress to stderr unless ``--json`` asked for a clean stdout."""
    if not quiet:
        print(message, file=sys.stderr)


def main(
    argv: list[str] | None = None,
    *,
    deployer: Callable[[pub.FirebaseHost], DeployOutcome] | None = None,
    builder: Callable[[], tuple[bool, str]] | None = None,
    live_checker: Callable[[pub.FirebaseHost, dict[str, Any]], str] | None = None,
) -> int:
    """Run the publication transaction.

    The three side-effecting steps are injectable — ``deployer`` (Firebase), ``builder``
    (``build_data.py``), ``live_checker`` (the HTTP fetch). Defaults are the real
    implementations; the tests pass fakes. That is what makes the whole sequence, including the
    database writes and the ordering guarantees, testable without a Firebase project or a
    network — and an untested publication path is one nobody would dare run.
    """
    args = build_parser().parse_args(argv)
    quiet = args.json
    deploy = deployer or (lambda host: firebase_deploy(host, site_root=pub.SITE_ROOT))
    build = builder or run_build_data
    live_check = live_checker or (lambda host, receipt: check_live_site(host, receipt))

    # ── P0 guard ─────────────────────────────────────────────────────────────────────────
    # Named before any work is done, so an operator-less invocation fails in a second rather
    # than after a ten-minute data build.
    if not args.dry_run and not args.operator:
        print(
            "publish: --operator is required for a real publication (deploying the website is a "
            "P0 controller-only action). Use --dry-run to see the plan without deploying.",
            file=sys.stderr,
        )
        return EXIT_PRECONDITION_FAILED

    # ── Step 1: the candidate is the checkout ────────────────────────────────────────────
    head = read_head_sha()
    problem = verify_candidate_sha(args.candidate_sha, head=head)
    if problem:
        print(f"publish: {problem}", file=sys.stderr)
        return EXIT_PRECONDITION_FAILED
    _emit(f"[1/8] candidate {args.candidate_sha[:12]} is HEAD", quiet=quiet)

    # ── Step 2: projections ──────────────────────────────────────────────────────────────
    # Read-only: a publisher observes the control plane's freshness, it does not create it.
    try:
        read_db = ControlDB.open_read_only(args.db)
    except ControlDBError as exc:
        print(
            f"publish: {exc}\n"
            "publish: refusing — without the control database there is no way to know whether "
            "the knowledge projections behind this data are current.",
            file=sys.stderr,
        )
        return EXIT_NO_CONTROL_DB
    with read_db:
        gate = pub.verify_projections(
            read_db,
            max_lag=args.max_lag,
            allow_unreported=args.allow_unreported_projections,
        )
    _emit("[2/8] " + pub.format_projection_gate(gate).replace("\n", "\n      "), quiet=quiet)
    if not gate.ok:
        # Refuse EARLY, before spending a data build on a tree we already know we will not ship.
        print(
            "publish: refusing — projections are not publishable:\n  - "
            + "\n  - ".join(gate.blockers),
            file=sys.stderr,
        )
        return EXIT_PRECONDITION_FAILED

    # ── Step 3: build the data ───────────────────────────────────────────────────────────
    if args.skip_build:
        _emit("[3/8] build skipped (--skip-build): verifying the data.js already present", quiet=quiet)
    else:
        ok, output = build()
        if not ok:
            print(f"publish: build_data.py failed:\n{output}", file=sys.stderr)
            return EXIT_PRECONDITION_FAILED
        _emit("[3/8] data.js rebuilt", quiet=quiet)

    # ── Step 4: HTML consistency ─────────────────────────────────────────────────────────
    try:
        data = pub.load_data_js()
        consistency = pub.check_site_consistency(data=data)
    except pub.PublicationError as exc:
        print(f"publish: {exc}", file=sys.stderr)
        return EXIT_PRECONDITION_FAILED
    _emit("[4/8] " + pub.format_consistency_report(consistency).replace("\n", "\n      "), quiet=quiet)

    # ── Step 5: the receipt ──────────────────────────────────────────────────────────────
    receipt = pub.build_receipt(
        repo_sha=head,
        data=data,
        projection_gate=gate,
        consistency=consistency,
        operator=args.operator,
        run_id=args.run_id,
        dry_run=args.dry_run,
    )
    # Relaxations are recorded, so a receipt produced under a loosened gate can never be
    # mistaken for one produced under the strict default.
    receipt.setdefault("projection_policy", {})
    receipt["projection_policy"].update(
        {"max_lag": args.max_lag, "allow_unreported": bool(args.allow_unreported_projections)}
    )
    try:
        pub.assert_publication_ready(
            projection_gate=gate, consistency=consistency, receipt=receipt
        )
    except pub.PublicationError as exc:
        print(f"publish: refusing —\n{exc}", file=sys.stderr)
        return EXIT_PRECONDITION_FAILED
    _emit(f"[5/8] receipt {pub.SCHEMA_ID} valid ({pub.receipt_sha256(receipt)[:12]}…)", quiet=quiet)

    # ── Dry run stops here — before the first side effect ────────────────────────────────
    if args.dry_run:
        _emit("[6/8] DRY RUN — would deploy, in order:", quiet=quiet)
        for host in pub.FIREBASE_HOSTS:
            cmd = "firebase deploy --only hosting" + (
                "" if host.role == "canonical" else f" --project {host.project}"
            )
            _emit(f"        {host.role:<9} {cmd}  (cwd {pub.SITE_ROOT})", quiet=quiet)
            _emit(f"                  {host.note}", quiet=quiet)
        _emit("[7/8] DRY RUN — would record the receipt + 2 deployment rows", quiet=quiet)
        _emit("[8/8] DRY RUN — would verify both live sites serve this data.js", quiet=quiet)
        _emit("publish: dry run complete — nothing was built into the database, nothing deployed",
              quiet=quiet)
        print(pub.serialise_receipt(receipt) if args.json else "DRY RUN: no deployment performed")
        return EXIT_OK

    # ── Step 6: deploy BOTH hosts ────────────────────────────────────────────────────────
    # Both are attempted even if the first fails: the operator needs to know the state of both
    # hosts, and stopping early would leave the second one's status unknown as well as unchanged.
    outcomes = []
    for host in pub.FIREBASE_HOSTS:
        _emit(f"[6/8] deploying {host.role} ({host.project})…", quiet=quiet)
        outcome = deploy(host)
        outcomes.append(outcome)
        _emit(
            f"      {host.role}: {'ok' if outcome.ok else 'FAILED'}"
            + (f" release={outcome.release_id}" if outcome.release_id else ""),
            quiet=quiet,
        )

    # ── Step 7: record — receipt first, then one row per host ────────────────────────────
    # Recorded even when a deploy failed. A failed host that left no row would be invisible; a
    # failed host with a row is a fact the next operator can see and act on.
    receipt_path = pub.write_receipt(receipt, db_path=args.db)
    try:
        _emit(f"[7/8] receipt archived at {receipt_path.relative_to(ROOT)}", quiet=quiet)
    except ValueError:
        # A --db override may point the receipt archive outside the repo (a tmp db in
        # tests); an absolute path is still honest.
        _emit(f"[7/8] receipt archived at {receipt_path}", quiet=quiet)
    try:
        with ControlDB.open(args.db) as db:
            record = db.record_publication_receipt(
                repo_sha=head,
                receipt=receipt,
                run_id=args.run_id,
                operator=args.operator,
                receipt_sha256=pub.receipt_sha256(receipt),
            )
            for outcome in outcomes:
                db.record_deployment(
                    record.receipt_id,
                    host_role=outcome.host.role,
                    firebase_project=outcome.host.project,
                    release_id=outcome.release_id,
                    hosting_url=outcome.host.url,
                    status="succeeded" if outcome.ok else "failed",
                    detail=outcome.detail,
                )
        _emit(f"      recorded receipt {record.receipt_id} + {len(outcomes)} deployments", quiet=quiet)
    except ControlDBError as exc:
        # The deploys already happened; failing to record them is serious but must not be
        # reported as "nothing was published".
        print(f"publish: WARNING — deployed but could not record: {exc}", file=sys.stderr)

    failed = [o for o in outcomes if not o.ok]
    if failed:
        print(
            "publish: deploy FAILED for: "
            + ", ".join(f"{o.host.role} ({o.host.project})" for o in failed)
            + " — the hosts have drifted; re-run once the cause is fixed.",
            file=sys.stderr,
        )
        if args.json:
            print(pub.serialise_receipt(receipt))
        return EXIT_DEPLOY_FAILED

    # ── Step 8: post-deploy check ────────────────────────────────────────────────────────
    if args.no_post_deploy_check:
        _emit("[8/8] post-deploy check skipped (--no-post-deploy-check)", quiet=quiet)
    else:
        problems = [p for p in (live_check(h, receipt) for h in pub.FIREBASE_HOSTS) if p]
        if problems:
            print("publish: post-deploy check failed:\n  - " + "\n  - ".join(problems), file=sys.stderr)
            if args.json:
                print(pub.serialise_receipt(receipt))
            return EXIT_POST_DEPLOY_FAILED
        _emit("[8/8] both hosts serve the receipted data.js", quiet=quiet)

    if args.json:
        print(pub.serialise_receipt(receipt))
    else:
        print(
            f"published {head[:12]} to {len(pub.FIREBASE_HOSTS)} hosts "
            f"(receipt {pub.receipt_sha256(receipt)[:12]}…, sessions_total="
            f"{receipt.get('sessions_total')})"
        )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
