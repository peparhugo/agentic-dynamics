---
status: accepted
---

# Branch protection — main (cap_stabilization_release p4)

**Status: APPLIED** — the settings below were applied to `peparhugo/agentic-dynamics`
branch `main` on 2026-08-26 via `gh api -X PUT repos/{owner}/{repo}/branches/main/protection`
(not merely spec'd). The live state is re-verifiable at any time with:

```bash
gh api repos/peparhugo/agentic-dynamics/branches/main/protection
```

## Why this exists

The stabilization review's P0 finding: the last 3 pushes to `main` failed "Tests & Lint",
and because lint gated tests *inside one job*, the deterministic suite never ran on the
current tip. The fix is two-fold (hard rule 7, `workflows/repository/cap_stabilization_release.yaml`):

1. **Independent required jobs** (`.github/workflows/pytest.yml`) — `lint`, `test`, `repro`,
   `packaging`. A lint failure can no longer hide test results.
2. **Branch protection requiring all four** — a merge to `main` is blocked until each job is
   green on the *up-to-date* head.

## Applied settings (exact)

| Setting | Value | Review requirement |
|---|---|---|
| Required checks | `lint`, `test`, `repro`, `packaging` | "required checks incl. the four jobs" |
| `required_status_checks.strict` | `true` (up-to-date branches: the head must be up to date with the base before merge) | "up-to-date branches" |
| `enforce_admins` | `true` (protection applies to administrators) | "protections applying to admins" |
| `required_pull_request_reviews.required_approving_review_count` | `1` | "PR-only" — `main` changes flow through reviewed pull requests |
| `required_pull_request_reviews.dismiss_stale_reviews` | `true` | pushes invalidate prior approvals |
| `required_linear_history` | `false` | merges may use merge commits (preserved from prior state) |
| `allow_force_pushes` | `false` | no force pushes (preserved) |
| `allow_deletions` | `false` | branch cannot be deleted (preserved) |
| `required_conversation_resolution` | `false` | preserved from prior state |
| `restrictions` | `null` | not applicable on the default branch |

"Automation included": GitHub applies required checks to *all* pushes to the protected branch,
including bot/automation identities — there is no per-app bypass in the branch-protection API
(that is a ruleset feature, out of scope here). An automation push that satisfies the four
required checks and a review may merge like any contributor.

## Job → gate mapping (`pytest.yml`)

| Job | Owns |
|---|---|
| `lint` | `ruff check .` — the whole active surface incl. `scripts/archive/` (archive policy: **lint-clean, not excluded**, `scripts/CONTEXT.md`) |
| `test` | Deterministic suite `pytest tests/ -m "not external" --timeout=600`; `build_data.py --dry-run`; `sync_data.py --check` (parquet parity); import gate (`import agentic_dynamics`, `import build_data`) |
| `repro` | `reproduce.sh --dry-run` core/opt-in split; clean Docker build; container CORE run regenerates `data.js` + `data_manifest.json` |
| `packaging` | wheel build + clean-venv install; `--help` documents checkout-only; dispatch emits "checkout required" with non-zero exit |
