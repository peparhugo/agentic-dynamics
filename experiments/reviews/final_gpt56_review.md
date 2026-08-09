# Final UX/UI Review: AI FinOps Framework

**Date:** August 9, 2026  
**Verdict:** Visually credible and much improved, but not ready for public launch.

## 1. 3-Second Impression

**Homepage: PASS.** "Your AI bill is a black box. This framework opens it." immediately establishes the problem, audience, and value. The restrained dark visual system, four proof points, and one dominant CTA feel focused and credible.

**Secondary pages: MIXED.** Evidence opens with a dense corpus/provenance paragraph before the result (`firebase/public/evidence.html:65-81`), while Apply leads with the vague phrase "FinOps engine" and defines the actual open-source harness only in the next section (`firebase/public/accelerator.html:101-116`).

## 2. Remaining Issues

| Priority | Issue | File:lines |
|---|---|---|
| **P0** | **Live KPIs visibly undermine trust.** `cost` already includes `$`, while the HTML adds another, rendering `$$64.98`. The hero also changes from `93.2%` to `88.7% (1572/1772)` after load, and the site still alternates among 249 sessions, 248 sessions, 227 experiments, 224 reports, and 203 reports without a stable taxonomy. | `firebase/public/app.js:28-40`; `firebase/public/index.html:50-57,122`; `firebase/public/evidence.html:67-72,144,156,230`; `firebase/public/data.js:11-15,537-548` |
| **P0** | **The calculator presents wrong labels as results.** Generated data places Claude at index 7, but the UI treats `costs[5]` as Claude. The escalation slider has four labels but indexes an eight-tier data array, so its displayed tier and cost calculation diverge. The "Show how" handler also renames the first mode button instead of the clicked disclosure. | `firebase/public/data.js:458-531`; `firebase/public/framework.html:203-222,353-376,382` |
| **P1** | **Mobile chrome obstructs content.** The fixed nav wraps to two rows while Story reduces top padding to 3rem, clipping the opening headline. The fixed theme toggle can overlap text and controls. | `firebase/public/base.css:72-86,210-219,228-239`; `firebase/public/story.html:10,34,42-45` |
| **P1** | **Global navigation remains misleading.** "Framework" links to the homepage, not `framework.html`, so the actual rules page is absent from global navigation. The Model Profiles CTA targets `#models`, but the destination section has no matching ID. | `firebase/public/index.html:47`; `firebase/public/framework.html:82,242`; `firebase/public/evidence.html:260-265` |
| **P1** | **Accessibility is unfinished.** Interactive elements have hover styling but no visible keyboard focus treatment; active navigation is color-only; several labels are 0.62-0.75rem in low-contrast gray. | `firebase/public/base.css:81-86,181-185,196-219`; `firebase/public/evidence.html:36-37`; `firebase/public/framework.html:203-222` |

## 3. Launch Readiness

**HOLD.** The site is close to an open research beta, but the KPI and calculator defects are launch blockers because they make the interface appear unreliable. Fix both P0 items, then resolve mobile clipping, navigation, and keyboard focus before public release. After those changes, the UX is launch-ready for a research framework; the enterprise positioning still needs claim validation outside this UX review.
