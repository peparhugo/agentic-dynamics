# Deploy gate — cap_site_revamp4_diagrams (p4_deploy)

**Verdict: FAIL — the operator's signed visual approval does not exist. No deploy.**
Phase: `p4_deploy` (the only phase that may deploy, and only after the signed
visual-approval artifact exists at the contract path). Hard rule 5: no deploy
without operator visual approval; the deploy lesson from the revamp4 campaign.

## The contract condition (p4 spec)

> THE ONLY PHASE THAT MAY DEPLOY — and ONLY after the operator's signed visual-approval
> artifact exists at the contract path (committed after the p3 checkpoint commit,
> non-placeholder signature — the checkpoint machinery).
> If the deployed gate fails **or the approval is absent**, the phase fails with the evidence.

## Evidence — the approval artifact is AWAITING (absent)

Contract path: `apps/website/verification/APPROVAL.md` (the p3 / p3b approval artifact).

| Check | State at HEAD (`b81413c7b`, p3b_craft_ux_pass) |
|---|---|
| Status line | `**Status: AWAITING operator re-review (2026-08-27). No deploy.**` |
| Decision box | `[ ] APPROVE` and `[ ] REJECT` — **neither checked** |
| Operator name | blank placeholder `______________________________________` |
| Signature / token | blank placeholder `______________________________________` |
| Prior record | REJECTED 2026-08-27 (eight-planes unclear, instrument-cycle contrast, one-engine-two-modes "UI not UX") — **stays on record** |
| Any `[x] APPROVE` in `verification/` | none (grep: no matches) |
| Any signature in `approvals/` | only `p2_design_with_human_checkpoint_approval.md` (`SIGNED-BY-OPERATOR: peparhugo` on 2026-08-27) — that is the **design** approval (authorizes implementation), **not** the p3b **visual** approval for this repaired build |
| Git notes / other channels | none (`git notes list` empty) |

The p2 design approval authorizes the *design* (approvals/cap_site_revamp4/
p2_design_with_human_checkpoint_approval.md, rev 2f9844797). It does not satisfy the
deploy gate: the p3b build was REJECTED and the approval artifact was reset to awaiting
at the p3b checkpoint. A non-placeholder APPROVE decision, committed after the p3b
checkpoint commit, is required before any `firebase deploy`.

## What was NOT done (deploy is forbidden by the gate)

- **No** `firebase deploy --only hosting` (canonical `ai-finops-rulebook`).
- **No** `firebase deploy --only hosting --project agentic-dynamics` (mirror).
- **No** data-chain rebuild for the purpose of deployment.
- **No** deployed-URL SVG gate run — there is no new deployment to gate.

The live site is untouched and remains the previously approved main build.

## What unblocks this phase

1. The operator visually re-reviews the p3b pack (`apps/website/verification/`:
   screenshots + `index.md` per-figure table + `gate_report_full.md`), then signs
   `apps/website/verification/APPROVAL.md` with a non-placeholder `[x] APPROVE`,
   operator name, date, and signature token.
2. The signed artifact is committed **after** the p3b checkpoint commit (`b81413c7b`).
3. p4 re-runs: data chain fresh → deploy BOTH hosts from `apps/website/` → re-run
   `verify_svg_rendering.py` against the DEPLOYED URLs → record PASS/FAIL.

## LOG

- Deploy: **not executed** (approval absent — gate failed before any deploy).
- Local rendering gate (p3b state, pre-deploy): **PASS** 22/22 SVGs, all 9 pages,
  1440x900 + 390x844, min text contrast 8.37:1 (see `verification/gate_report_full.md`).
- Deployed-URL gate: **not run** (no deployment).
- Phase verdict: **FAIL** — the approval-absent fail condition in the p4 spec.
