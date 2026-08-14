# Operational Framework Facelift Verification

Comparison basis: `firebase/public/framework.html` at `HEAD` versus `HEAD~1`. Data source: `firebase/public/data.js`.

## Checks

| Check | Result | Evidence |
|---|---|---|
| Every `data-stat` key resolves | **PASS** | All six referenced display keys resolve through `app.js`: `story_sessions` -> `summary.story_sessions`, `variants` -> `summary.variants`, `stories_total` -> `summary.stories_total`, `story_total_cost` -> `summary.story_total_cost`, and `woc`/`woc_percent` -> `calculator.woc_ratio`. All source paths exist in `data.js`. |
| Measured numbers and calculator fallbacks are unchanged | **PASS** | The `HEAD~1` diff preserves every measured magnitude. The EPM scenarios, model-cost fallback, escalation-tier fallback, and all 14 range-input `min`/`max`/`value`/`step` contracts are unchanged. The calculator now selects `costs[costs.length - 1]` instead of fixed index `7`; this changes no fallback value and safely supports the seven-entry live dataset and eight-entry fallback. |
| Inline SVG is valid and self-contained | **PASS** | Both SVG payloads parse as XML with valid `<svg>` roots and closed tags. The architecture diagram has no external references; its gradients, marker, pattern, and filter use resolved internal fragment IDs. |
| Function references and script order are intact | **PASS** | `buildChart`, `rebuildChart`, `setCalcMode`, `toggleHow`, `updateChartToggle`, and `updateROI` are present. Script order is unchanged: Chart.js, `data.js`, the inline calculator/chart script, then `app.js`; no script was removed or reordered. |
| Internal anchors resolve | **PASS** | Every named hash link resolves to a page ID (`#architecture`, `#calculator`, and `#playbook`). The seven bare `href="#"` chart controls are intentional JavaScript controls whose handlers return `false`; there are no missing named targets. |

## Number Summary

No measured number or calculator fallback changed. New or repositioned numerals in the diff are structural labels, CSS/SVG geometry, or duplicated presentation of existing values; they do not alter a measured or calculated magnitude.

## Test Result

`python3 -m pytest tests/`: **437 passed, 0 failed, 1 skipped** in 341.69 seconds.
