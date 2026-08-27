---
status: accepted
---
# Branch protection — main (cap_stabilization_release p4, reconciled review P1)

**Status: APPLIED** — the settings below were applied to `peparhugo/agentic-dynamics`
branch `main` on 2026-08-26 via `gh api -X PUT repos/{owner}/{repo}/branches/main/protection`
(not merely spec'd), then **reconciled with the live state on 2026-08-28** (review P1:
the committed doc claimed administrator enforcement and a required review; the live
config never had either). The live state is re-verifiable at any time with:

```bash
python3 scripts/check_branch_protection.py        # drift check — exit 1 on mismatch
gh api repos/peparhugo/agentic-dynamics/branches/main/protection
```

The drift check is the release-time reconciliation: `main` is not "clean" while it
reports DRIFT. (`scripts/check_branch_protection.py`'s `EXPECTED` block is the
machine-readable twin of the table below — keep them in lockstep.)

## Why this exists

The stabilization review's P0 finding: the last 3 pushes to `main` failed "Tests & Lint",
and because lint gated tests *inside one job*, the deterministic suite never ran on the
current tip. The fix is two-fold (hard rule 7, `workflows/repository/cap_stabilization_release.yaml`):

1. **Independent required jobs** (`.github/workflows/pytest.yml`) — `lint`, `test`, `repro`,
   `packaging`. A lint failure can no longer hide test results.
2. **Branch protection requiring all four** — a merge to `main` is blocked until each job is
   green on the *up-to-date* head.

## The two-tier access model (honest, not accidental)

The repo is a solo-dev shape with an experiment-runner identity, so protection is
two-tier and the settings below say so:

```
ordinary contributor:
    PR + all four required checks (non-admin enforcement)
experiment runner / operator:
    privileged direct push (admin override — enforce_admins is OFF)
    + mandatory post-push checks on every push (GitHub applies required checks
      to all pushes, including bot/automation identities — there is no per-app
      bypass in the branch-protection API)
    + CI failure as the rollback signal: a red push is visible immediately
    + the release-time drift check above
```

`enforce_admins: false` is deliberate: the operator's direct pushes are the privileged
path (the campaign machinery commits to `main` between phases), and the four required
checks + loud CI are its safety net — not a review requirement (zero required reviews,
the solo-dev shape).

## Applied settings (exact — verified live 2026-08-28)

| Setting | Value | Notes |
|---|---|---|
| Required checks | `lint`, `test`, `repro`, `packaging` | verified live (all four contexts present) |
| `required_status_checks.strict` | `true` | up-to-date branches: the head must be up to date with the base before merge |
| `enforce_admins` | `false` | the operator/runner's privileged direct-push path (admin override) |
| `required_pull_request_reviews.required_approving_review_count` | `0` | solo-dev shape — no required reviews; contributors still merge via PR |
| `required_pull_request_reviews.dismiss_stale_reviews` | `true` | pushes invalidate prior approvals |
| `required_linear_history` | `false` | merges may use merge commits |
| `allow_force_pushes` | `false` | no force pushes (preserved) |
| `allow_deletions` | `false` | branch cannot be deleted (preserved) |
| `required_conversation_resolution` | `false` | preserved |
| `required_signatures` | `false` | preserved |

## Job → gate mapping (`pytest.yml`)

| Job | Owns |
|---|---|
| `lint` | `ruff check .` — the whole active surface incl. `scripts/archive/` (archive policy: **lint-clean, not excluded**, `scripts/CONTEXT.md`) |
| `test` | Deterministic suite `pytest tests/ -m "not external" --timeout=600`; `build_data.py --dry-run`; `sync_data.py --check` (parquet parity); import gate (`import agentic_dynamics`, `import build_data`) |
| `repro` | `reproduce.sh --dry-run` core/opt-in split; clean Docker build; container CORE run regenerates `data.js` + `data_manifest.json` |
| `packaging` | wheel build + clean-venv install; `--help` documents checkout-only; dispatch emits "checkout required" with non-zero exit |
