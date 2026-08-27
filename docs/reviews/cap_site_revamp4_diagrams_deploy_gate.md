---
status: accepted
---
# Deploy gate — cap_site_revamp4_diagrams (p4_deploy)

**Verdict: PASS — the operator's signed visual approval exists and BOTH hosts were
deployed; the deployed-URL rendering gate passes 22/22 on both projects.**
Phase: `p4_deploy` (the only phase that may deploy, and only after the signed
visual-approval artifact exists at the contract path). Hard rule 5: no deploy
without operator visual approval; the deploy lesson from the revamp4 campaign.

## History — first attempt FAILED (approval absent), second attempt PASSED

The p4 phase first ran at HEAD `b81413c7b` (p3b_craft_ux_pass): the approval
artifact was still AWAITING (the operator had REJECTED the first craft pass), so the
phase failed the approval-absent condition and no deploy happened. That failure is
preserved below as the record. The operator then visually re-reviewed the p3b
re-craft, signed the approval artifact, and the commit `7bd1528e1`
("operator visual approval: APPROVED (peparhugo, 2026-08-27 — the p3b re-crafted
figures reviewed; deploy + merge authorized)") made the gate satisfiable. This
document records the re-run.

## The contract condition (p4 spec)

> THE ONLY PHASE THAT MAY DEPLOY — and ONLY after the operator's signed visual-approval
> artifact exists at the contract path (committed after the p3 checkpoint commit,
> non-placeholder signature — the checkpoint machinery).
> If the deployed gate fails **or the approval is absent**, the phase fails with the evidence.

## Evidence — the approval is GENUINE (signed, committed after the checkpoint)

Contract path: `apps/website/verification/APPROVAL.md`.

| Check | State at the p4 re-run |
|---|---|
| Approval commit | `7bd1528e1` "operator visual approval: APPROVED (peparhugo, 2026-08-27…)" — committed **after** the p3b checkpoint commit `b81413c7b` |
| Status line | `**Status: AWAITING operator re-review (2026-08-27). No deploy.**` → the artifact is now signed |
| Decision box | `[x] APPROVE — proceed to deploy` — the APPROVE box is checked |
| Operator name | `peparhugo` (non-placeholder) |
| Role / title | `Operator` |
| Date | `2026-08-27` |
| Signature / token | `peparhugo` (non-placeholder) |
| Prior record | REJECTED 2026-08-27 (figure-by-figure) stays on record; the p3b re-craft answered each point (see `verification/index.md` REJECT→redesign mapping) |
| p2 design approval | `approvals/cap_site_revamp4/p2_design_with_human_checkpoint_approval.md` (rev 2f9844797) authorizes the *design*; the visual gate additionally required and now has the p3b *visual* approval above |

## What WAS done (deploy executed, both hosts)

- Data chain regenerated fresh for the deploy: `scripts/inventory.py refresh` → `scripts/sync_data.py` → `scripts/build_data.py` → `scripts/generate_manifest.py` (committed `3f08b3be4`; `data.js` generated 2026-08-27T19:16:59Z, deployed and confirmed live).
- `firebase deploy --only hosting` → **ai-finops-rulebook** (canonical): `✔ Deploy complete` (44 files).
- `firebase deploy --only hosting --project agentic-dynamics` → **agentic-dynamics** (mirror): `✔ Deploy complete` (44 files).
- Mirror-identity check: all 9 pages sha256-identical across both hosts (no drift).

## Deployed-URL rendering gate (the p4 gate — run on the DEPLOYED pages)

`verify_svg_rendering.py --base <deployed URL> --pages index,framework,question,evidence,methodology,story,accelerator,databricks,glossary --mobile`:

| Host | SVGs checked | PASS | FAIL | min contrast | verdict |
|---|---|---|---|---|---|
| https://ai-finops-rulebook.web.app (canonical) | 22 | 22 | 0 | 8.37:1 | **PASS** |
| https://agentic-dynamics.web.app (mirror) | 22 | 22 | 0 | 8.37:1 | **PASS** |

Full per-SVG tables: `/tmp/site_scan/deployed_canonical/svg_render_report.md` and
`/tmp/site_scan/deployed_mirror/svg_render_report.md` (gate artifact at deploy time).

Before/after on the live URL: pre-deploy `ai-finops-rulebook.web.app/framework.html`
FAILED the gate — svg#1 `architecture-map` rendered **0x0** (SIZE + PAINT failures;
the revamp4 collapsed figure). Post-deploy the same URL passes 22/22; the collapsed
`architecture-map` is gone, replaced by six `diagram-map` figures in the approved
grammar (`workflow-map`, `planes`, `fw-cycle`, `twomodes`, `envelope`, `autonomy-map`).

## LOG

- Deploy (1st p4 attempt at `b81413c7b`): **not executed** — approval absent; phase FAIL recorded (this doc, prior revision).
- Approval: signed by operator peparhugo, committed `7bd1528e1` (after the checkpoint).
- Data chain: regenerated + committed `3f08b3be4`.
- Deploy: `ai-finops-rulebook` ✔ + `agentic-dynamics` ✔ (both 44 files, both release complete).
- Local rendering gate (pre-deploy, approved build): **PASS** 22/22 (see `verification/gate_report_full.md`).
- Deployed-URL gate: canonical **PASS** 22/22 · mirror **PASS** 22/22, min text contrast 8.37:1.
- Phase verdict: **PASS** — deploy gate satisfied and verified on the deployed pages.
