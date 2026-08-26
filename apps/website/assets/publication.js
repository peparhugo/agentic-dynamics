/*
 * Public publication helpers.
 *
 * Data is read only from data.js. The display labels deliberately distinguish
 * measured capture from computed per-model aggregates, following the R1 ledger.
 * This file owns no findings and never supplies a numeric fallback.
 */
(function () {
  "use strict";

  function formatUsd(value, digits) {
    return `$${Number(value).toFixed(digits === undefined ? 2 : digits)}`;
  }

  function setText(selector, value) {
    document.querySelectorAll(selector).forEach((element) => {
      element.textContent = value;
    });
  }

  function renderStats(data) {
    if (!data || !data.summary) return;
    const summary = data.summary;
    setText('[data-ad-stat="sessions"]', Number(summary.sessions_total).toLocaleString());
    setText('[data-ad-stat="stories"]', Number(summary.stories_total).toLocaleString());
    setText('[data-ad-stat="models"]', String(summary.variants));
    setText('[data-ad-stat="cost"]', formatUsd(summary.total_cost));
    setText('[data-ad-stat="providers"]', String(data.public_statistics.providers));
    setText('[data-ad-stat="findings"]', String(summary.canonical_findings));
  }

  function renderModelTable(data) {
    const target = document.querySelector('[data-ad-model-table]');
    if (!target || !data || !Array.isArray(data.models)) return;
    const rows = data.models.map((model) => {
      const cache = model.avg_cache_hit == null ? "not captured" : `${(model.avg_cache_hit * 100).toFixed(1)}%`;
      const tests = model.avg_tests == null ? "not captured" : Number(model.avg_tests).toFixed(1);
      const records = model.cost_captured_records == null ? "not captured" : `${model.cost_captured_records}/${model.total_records}`;
      return `<tr><td><strong>${model.label}</strong></td><td class="num">${formatUsd(model.avg_cost)}</td><td class="num">${tests}</td><td class="num">${cache}</td><td class="num">${records}</td></tr>`;
    }).join("");
    target.innerHTML = `<table class="ad-table"><caption>Current story-model aggregates [C] over captured story records [M]</caption><thead><tr><th>Model</th><th>Average cost/story</th><th>Average tests</th><th>Average cache hit</th><th>Cost records</th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  function renderDiagrams() {
    if (!window.AgenticDesign) return;
    const diagrams = {
      cycle: AgenticDesign.instrumentCycle,
      nxm: AgenticDesign.nxmProblem,
      planes: AgenticDesign.planesMap,
      engine: AgenticDesign.engineModes,
      autonomy: AgenticDesign.autonomyEnvelope,
      curves: AgenticDesign.costCurves,
      escalation: AgenticDesign.escalationChain,
      calibration: AgenticDesign.calibrationArc,
    };
    document.querySelectorAll('[data-ad-diagram]').forEach((figure) => {
      const makeDiagram = diagrams[figure.dataset.adDiagram];
      if (makeDiagram) figure.insertAdjacentHTML("afterbegin", makeDiagram());
    });
    const rules = document.querySelector("[data-ad-rules]");
    if (rules) {
      rules.innerHTML = AgenticDesign.rulesComponent();
      AgenticDesign.activateRuleCards(rules);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const data = window.DYNAMICS_DATA;
    renderStats(data);
    renderModelTable(data);
    renderDiagrams();
  });
}());
