/*
 * Agentic Dynamics public-site wiring v2.
 *
 * ``data.js`` is the single publication door. This module formats already
 * provenance-tagged values, renders inline SVG components, and binds accessible
 * rule cards; it never introduces a numeric fallback or invents a finding.
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

  function renderCampaignSlots(data) {
    const campaigns = data && data.campaigns;
    if (!campaigns) return;
    const cap2b = campaigns.cap_2b;
    const escalation = campaigns.escalation;
    const routing = campaigns.session_routing;
    const ci = cap2b.decision_rule.cpvo_ratio_ci_95;
    const decision = `Static n=${cap2b.static.n}, CPVO ${formatUsd(cap2b.static.cpvo_usd, 6)}, ${cap2b.static.accepted_outcomes}/${cap2b.static.n} verified; adaptive n=${cap2b.adaptive.n}, CPVO ${formatUsd(cap2b.adaptive.cpvo_usd, 6)}, ${cap2b.adaptive.accepted_outcomes}/${cap2b.adaptive.n} verified; CPVO ratio ${Number(cap2b.decision_rule.cpvo_ratio).toFixed(4)}, 95% CI [${Number(ci[0]).toFixed(4)}, ${Number(ci[1]).toFixed(4)}]; success gap ${Number(cap2b.decision_rule.success_gap_static_minus_adaptive).toFixed(4)}. The pre-registered rule decided ${cap2b.decision_rule.decision}.`;
    setText('[data-ad-cap2b-summary]', decision);
    setText('[data-ad-cap2b-source]', cap2b.source_artifact);

    const models = escalation.models;
    const escalationSummary = `[M] baseline ${formatUsd(escalation.baseline_cost_usd, 6)}; ${models.map((model) => `${model.escalation_model.split("/").pop()}: ${formatUsd(model.escalation_fix_cost_usd, 6)} [M], E_x=${Number(model.E_x).toFixed(4)} [C]`).join("; ")}.`;
    setText('[data-ad-escalation-summary]', escalationSummary);
    const escalationDefinition = `The measured campaign reports ${models.map((model) => `${model.escalation_model.split("/").pop()} at E_x=${Number(model.E_x).toFixed(4)} (n=${model.n_model_cells} model cell)`).join(" and ")}.`;
    setText('[data-ad-escalation-definition]', escalationDefinition);
    setText('[data-ad-escalation-n]', models.map((model) => `n=${model.n_model_cells} per model`).join(", "));
    setText('[data-ad-escalation-source]', escalation.source_artifact);

    const untriggered = routing.escalate_live;
    const untriggeredSummary = `All ${untriggered.n} live escalate cells completed on the first attempt. ${untriggered.untriggered}`;
    setText('[data-ad-untriggered-summary]', untriggeredSummary);
    setText('[data-ad-routing-source]', routing.source_artifact);
  }

  function renderDiagrams(data) {
    if (!window.AgenticDesign) return;
    const campaigns = data && data.campaigns ? data.campaigns : {};
    const diagrams = {
      cycle: AgenticDesign.instrumentCycle,
      nxm: AgenticDesign.nxmProblem,
      planes: AgenticDesign.planesMap,
      engine: AgenticDesign.engineModes,
      autonomy: AgenticDesign.autonomyEnvelope,
      curves: AgenticDesign.costCurves,
      escalation: () => AgenticDesign.escalationChain(campaigns.escalation),
      calibration: () => AgenticDesign.calibrationArc(campaigns.cap_2b),
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
    renderCampaignSlots(data);
    renderDiagrams(data);
  });
}());
