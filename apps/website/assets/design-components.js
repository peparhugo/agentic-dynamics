/*
 * Agentic Dynamics design components v1.
 *
 * The gallery uses this file as a source of inline SVG, rather than external images,
 * so each diagram remains selectable, accessible, printable, and easy to cite. The
 * functions intentionally contain no data fetching or rendering dependency; later
 * pages pass only already-provenanced display values into this visual layer.
 */
(function () {
  "use strict";

  const defs = `
    <defs>
      <marker id="ad-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#17212b"/></marker>
      <marker id="ad-arrow-measured" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#287271"/></marker>
      <marker id="ad-arrow-policy" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#8d4551"/></marker>
      <pattern id="ad-hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" stroke="#6f7477" stroke-width="2"/></pattern>
    </defs>`;

  let diagramCount = 0;

  function svg(title, description, body, viewBox) {
    // Every inline SVG needs unique IDs so a screen reader resolves its own title,
    // descriptions, markers, and pattern instead of a preceding figure's elements.
    const suffix = `-${++diagramCount}`;
    // Placeholders avoid the shorter "ad-arrow" token rewriting the longer IDs.
    const scopeIds = (markup) => markup
      .replaceAll("ad-arrow-policy", "AD_POLICY")
      .replaceAll("ad-arrow-measured", "AD_MEASURED")
      .replaceAll("ad-arrow", "AD_ARROW")
      .replaceAll("ad-hatch", "AD_HATCH")
      .replaceAll("AD_POLICY", `ad-arrow-policy${suffix}`)
      .replaceAll("AD_MEASURED", `ad-arrow-measured${suffix}`)
      .replaceAll("AD_ARROW", `ad-arrow${suffix}`)
      .replaceAll("AD_HATCH", `ad-hatch${suffix}`);
    const scopedDefs = scopeIds(defs);
    // Marker and pattern URLs must be attributes/styles on this instance; CSS cannot
    // safely address a different marker ID for every inline figure.
    const scopedBody = scopeIds(body)
      .replaceAll("class=\"flow-policy\"", `class="flow-policy" marker-end="url(#ad-arrow-policy${suffix})"`)
      .replaceAll("class=\"flow-measured\"", `class="flow-measured" marker-end="url(#ad-arrow-measured${suffix})"`)
      .replaceAll("class=\"flow\"", `class="flow" marker-end="url(#ad-arrow${suffix})"`)
      .replaceAll("class=\"node-null\"", `class="node-null" style="fill:url(#ad-hatch${suffix})"`);
    return `<svg class="ad-diagram" viewBox="${viewBox || "0 0 760 360"}" role="img" aria-labelledby="ad-title${suffix} ad-desc${suffix}"><title id="ad-title${suffix}">${title}</title><desc id="ad-desc${suffix}">${description}</desc>${scopedDefs}${scopedBody}</svg>`;
  }

  function instrumentCycle() {
    return svg("The Agentic Dynamics instrument cycle", "A five-step cycle where instrumented events are derived into information before policy is written and tested.", `
      <rect class="frame" x="12" y="12" width="736" height="336" rx="14"/>
      <text class="micro" x="36" y="42">FIELD METHOD / ONE IDEA</text>
      <path class="flow-measured" d="M215 122C310 55 460 55 547 122"/>
      <path class="flow-measured" d="M590 160C640 218 612 284 545 292"/>
      <path class="flow-policy" d="M490 292C406 332 274 332 208 292"/>
      <path class="flow-policy" d="M164 254C102 198 110 146 170 122"/>
      <g transform="translate(108 92)"><circle class="node-measured" cx="58" cy="58" r="48"/><text class="label" x="58" y="55" text-anchor="middle">1 Instrument</text><text class="small" x="58" y="71" text-anchor="middle">capture events</text><text class="tag-m" x="58" y="89" text-anchor="middle">[M]</text></g>
      <g transform="translate(300 48)"><circle class="node-measured" cx="78" cy="58" r="48"/><text class="label" x="78" y="55" text-anchor="middle">2 Derive</text><text class="small" x="78" y="71" text-anchor="middle">name information</text><text class="tag-m" x="78" y="89" text-anchor="middle">[M] -> [C]</text></g>
      <g transform="translate(515 92)"><circle class="node-policy" cx="58" cy="58" r="48"/><text class="label" x="58" y="55" text-anchor="middle">3 Write policy</text><text class="small" x="58" y="71" text-anchor="middle">consume signals</text><text class="tag-p" x="58" y="89" text-anchor="middle">[P]</text></g>
      <g transform="translate(450 214)"><circle class="node-policy" cx="58" cy="58" r="48"/><text class="label" x="58" y="55" text-anchor="middle">4 Grid</text><text class="small" x="58" y="71" text-anchor="middle">compare arms</text><text class="tag-p" x="58" y="89" text-anchor="middle">[P]</text></g>
      <g transform="translate(205 214)"><circle class="node-computed" cx="58" cy="58" r="48"/><text class="label" x="58" y="55" text-anchor="middle">5 Campaign</text><text class="small" x="58" y="71" text-anchor="middle">change one factor</text><text class="tag-c" x="58" y="89" text-anchor="middle">[C]</text></g>
      <text class="small" x="380" y="180" text-anchor="middle">No policy consumes information that the instrument did not produce.</text>`);
  }

  function nxmProblem() {
    return svg("N by M evidence surface", "Linked sessions cross independent measurement angles, then analysis creates a second evidence burden.", `
      <rect class="frame" x="12" y="12" width="736" height="336" rx="14"/>
      <text class="micro" x="36" y="42">WHY ONE TASK IS NOT ENOUGH</text>
      <text class="label" x="72" y="86">N linked sessions</text><text class="small" x="72" y="103">Each output becomes the next context.</text>
      <text class="label" x="480" y="86">M measurement angles</text><text class="small" x="480" y="103">Tests alone do not establish durable value.</text>
      <path class="flow" d="M235 146H330"/><path class="flow" d="M430 146H515"/>
      <g transform="translate(72 130)"><rect class="node" width="164" height="44" rx="6"/><text class="label" x="82" y="19" text-anchor="middle">S1 -> S2 -> ... -> SN</text><text class="small" x="82" y="34" text-anchor="middle">inherited codebase</text></g>
      <g transform="translate(330 120)"><rect class="node-computed" width="100" height="64" rx="6"/><text class="label" x="50" y="27" text-anchor="middle">N x M</text><text class="tag-c" x="50" y="45" text-anchor="middle">surface</text></g>
      <g transform="translate(515 130)"><rect class="node" width="174" height="44" rx="6"/><text class="label" x="87" y="19" text-anchor="middle">quality | cost | recovery</text><text class="small" x="87" y="34" text-anchor="middle">verification | uncertainty</text></g>
      <rect x="84" y="222" width="580" height="70" rx="8" fill="url(#ad-hatch)" stroke="#6f7477"/>
      <text class="label" x="374" y="250" text-anchor="middle">A second burden: analyze across factors, commits, and positions.</text>
      <text class="small" x="374" y="270" text-anchor="middle">Hatched surface = method map, not a measured count. [P]</text>`);
  }

  function planesMap() {
    const planes = ["core", "experiment", "measurement", "runtime", "adapters", "knowledge", "control", "reporting"];
    const boxes = planes.map((name, index) => {
      const x = 42 + (index % 4) * 174;
      const y = 92 + Math.floor(index / 4) * 112;
      const cls = name === "control" ? "node-policy" : name === "measurement" ? "node-measured" : "node";
      return `<g transform="translate(${x} ${y})"><rect class="${cls}" width="142" height="70" rx="8"/><text class="micro" x="14" y="20">PLANE 0${index + 1}</text><text class="label" x="14" y="46">${name}</text></g>`;
    }).join("");
    return svg("Eight planes of Agentic Dynamics", "The eight package planes are arranged as a dependency-aware map. Control is downstream of information-producing planes.", `
      <rect class="frame" x="12" y="12" width="736" height="336" rx="14"/>
      <text class="micro" x="36" y="42">PLATFORM MAP / DEPENDENCY DIRECTION</text>
      <path class="guide" d="M74 76H686"/><text class="small" x="74" y="66">Foundation and execution planes produce the information that control consumes.</text>
      ${boxes}
      <path class="flow-measured" d="M286 162V204"/><path class="flow-policy" d="M460 204V162"/>
      <text class="tag-m" x="299" y="190">measure</text><text class="tag-p" x="472" y="190">control</text>
      <text class="small" x="42" y="304">Architecture map only [P]. It describes ownership, not system performance.</text>`);
  }

  function engineModes() {
    return svg("One engine, two operating modes", "Fixed factors produce one operating cell; varied factors produce a grid, but both run through the same execution engine.", `
      <rect class="frame" x="12" y="12" width="736" height="336" rx="14"/>
      <text class="micro" x="36" y="42">OPERATE OR EXPERIMENT</text>
      <g transform="translate(42 78)"><rect class="node" width="172" height="72" rx="8"/><text class="micro" x="14" y="20">OPERATE</text><text class="label" x="14" y="43">Fixed factors</text><text class="small" x="14" y="59">1 selected cell</text></g>
      <g transform="translate(42 204)"><rect class="node-computed" width="172" height="72" rx="8"/><text class="micro" x="14" y="20">EXPERIMENT</text><text class="label" x="14" y="43">Varied factors</text><text class="small" x="14" y="59">G controlled cells [C]</text></g>
      <path class="flow" d="M214 114H286M214 240H286"/>
      <g transform="translate(286 140)"><rect class="node-measured" width="132" height="72" rx="36"/><text class="label" x="66" y="36" text-anchor="middle">CELL</text><text class="small" x="66" y="53" text-anchor="middle">shared unit</text></g>
      <path class="flow-measured" d="M418 176H476M574 176H624"/>
      <g transform="translate(476 140)"><rect class="node-measured" width="98" height="72" rx="8"/><text class="label" x="49" y="34" text-anchor="middle">ENGINE</text><text class="small" x="49" y="52" text-anchor="middle">jobs</text></g>
      <g transform="translate(624 140)"><rect class="node" width="88" height="72" rx="8"/><text class="label" x="44" y="34" text-anchor="middle">LEDGER</text><text class="small" x="44" y="52" text-anchor="middle">events</text></g>
      <path class="flow-policy" d="M668 212V262H340"/><text class="tag-p" x="500" y="253">only G > 1: compare arms -> adapt</text>`);
  }

  function autonomyEnvelope() {
    return svg("Bounded autonomy envelope", "Human policy defines constraints around a bounded autonomous execution and independent verification path.", `
      <rect class="frame" x="12" y="12" width="736" height="336" rx="14"/>
      <text class="micro" x="36" y="42">BOUNDED AUTONOMY / POLICY MAP</text>
      <rect x="48" y="72" width="664" height="220" rx="14" fill="#fffdf8" stroke="#8d4551" stroke-width="2" stroke-dasharray="8 5"/>
      <text class="tag-p" x="66" y="94">[P] HUMAN-DECLARED POLICY BOUNDARY</text>
      <g transform="translate(78 132)"><rect class="node-policy" width="132" height="74" rx="8"/><text class="label" x="66" y="33" text-anchor="middle">Constraints</text><text class="small" x="66" y="52" text-anchor="middle">budget | scope | halt</text></g>
      <path class="flow-policy" d="M210 169H280"/>
      <g transform="translate(280 132)"><rect class="node" width="132" height="74" rx="8"/><text class="label" x="66" y="33" text-anchor="middle">Execute</text><text class="small" x="66" y="52" text-anchor="middle">attempts</text></g>
      <path class="flow-measured" d="M412 169H482"/>
      <g transform="translate(482 132)"><rect class="node-measured" width="132" height="74" rx="8"/><text class="label" x="66" y="33" text-anchor="middle">Verify</text><text class="small" x="66" y="52" text-anchor="middle">independent test</text><text class="tag-m" x="66" y="65" text-anchor="middle">[M]</text></g>
      <path class="flow" d="M548 206V248H440"/><path class="flow-policy" d="M548 206V248H638"/>
      <text class="label" x="405" y="266">reject / rework</text><text class="label" x="642" y="266" text-anchor="middle">accept or halt</text>
      <text class="small" x="66" y="318">Typed checkpoints are not-run instrumentation, not an implied capability. [NULL]</text>`);
  }

  function costCurves() {
    return svg("Observed and modeled cost curves are separate", "The current corpus has no canonical story-arc lab output, while the cumulative curve is explicitly modeled from a beta assumption.", `
      <rect class="frame" x="12" y="12" width="736" height="336" rx="14"/>
      <text class="micro" x="36" y="42">COST SURFACES / DO NOT MERGE EVIDENCE CLASSES</text>
      <g transform="translate(50 78)"><rect class="node-null" width="286" height="188" rx="8"/><text class="label" x="18" y="30">Immediate story arc</text><text class="small" x="18" y="49">Current canonical lab output is absent.</text><path class="guide-dash" d="M38 150H248M38 150V72"/><text class="small" x="143" y="115" text-anchor="middle">not measured</text><text class="micro" x="18" y="172">[NULL] no published series</text></g>
      <g transform="translate(424 78)"><rect class="node-computed" width="286" height="188" rx="8"/><text class="label" x="18" y="30">Cumulative scenario</text><text class="small" x="18" y="49">C(N) = N + beta*N(N-1)/2</text><path class="guide" d="M38 150H248M38 150V72"/><path class="curve-computed" d="M42 145C96 142 144 130 181 105S234 52 246 36"/><text class="tag-c" x="158" y="77">[C] beta is an input</text><text class="small" x="18" y="172">model, not forecast</text></g>
      <text class="small" x="380" y="308" text-anchor="middle">A displayed curve must say whether it is observed, computed, or unavailable.</text>`);
  }

  function escalationChain(escalation) {
    // Campaign measurements arrive through data.js. Diagram structure is static;
    // values are never duplicated here as presentation fallbacks.
    const models = escalation && escalation.models ? escalation.models : [];
    const baseline = escalation ? escalation.baseline_cost_usd : null;
    const first = models[0] || {};
    const second = models[1] || {};
    const shortName = (model) => (model || "not loaded").split("/").pop().replace("gpt-5.6-", "").replace("claude-", "");
    const usd = (value) => value == null ? "not loaded" : `$${Number(value).toFixed(6)}`;
    const ratio = (value) => value == null ? "not loaded" : Number(value).toFixed(4);
    return svg("Measured escalation cost chain", "A baseline cell and two measured escalation fixes yield separate E_x ratios with per-model cell counts shown.", `
      <rect class="frame" x="12" y="12" width="736" height="336" rx="14"/>
      <text class="micro" x="36" y="42">MEASURED ESCALATION / PER-MODEL N VISIBLE</text>
      <g transform="translate(42 126)"><rect class="node-measured" width="136" height="88" rx="8"/><text class="label" x="68" y="34" text-anchor="middle">Baseline cell</text><text class="small" x="68" y="53" text-anchor="middle">${usd(baseline)} [M]</text><text class="tag-m" x="68" y="72" text-anchor="middle">critical defect</text></g>
      <path class="flow" d="M178 170H260"/>
      <g transform="translate(260 126)"><rect class="node" width="126" height="88" rx="8"/><text class="label" x="63" y="34" text-anchor="middle">Rejected</text><text class="small" x="63" y="53" text-anchor="middle">downstream risk</text><text class="small" x="63" y="70" text-anchor="middle">not a price list</text></g>
      <path class="flow-measured" d="M386 150H458M386 194H458"/>
      <g transform="translate(458 94)"><rect class="node-measured" width="210" height="78" rx="8"/><text class="label" x="16" y="30">${shortName(first.escalation_model)} fix: ${usd(first.escalation_fix_cost_usd)} [M]</text><text class="small" x="16" y="49">E_x = ${ratio(first.E_x)} [C]</text><text class="micro" x="16" y="66">n = ${first.n_model_cells == null ? "not loaded" : first.n_model_cells} / model</text></g>
      <g transform="translate(458 206)"><rect class="node-measured" width="210" height="78" rx="8"/><text class="label" x="16" y="30">${shortName(second.escalation_model)} fix: ${usd(second.escalation_fix_cost_usd)} [M]</text><text class="small" x="16" y="49">E_x = ${ratio(second.E_x)} [C]</text><text class="micro" x="16" y="66">n = ${second.n_model_cells == null ? "not loaded" : second.n_model_cells} / model</text></g>
      <text class="small" x="42" y="314">Ratios are descriptive measurements, not a provider recommendation.</text>`);
  }

  function calibrationArc(calibration, campaign) {
    const rerun = calibration && calibration.rerun ? calibration.rerun : {};
    const staticArm = campaign && campaign.static ? campaign.static : {};
    const adaptiveArm = campaign && campaign.adaptive ? campaign.adaptive : {};
    const decision = campaign && campaign.decision_rule ? campaign.decision_rule : {};
    const ci = decision.cpvo_ratio_ci_95 || [];
    const rerunCi = rerun.wilson_95_ci || [];
    const ratio = decision.cpvo_ratio == null ? "not loaded" : Number(decision.cpvo_ratio).toFixed(4);
    const interval = ci.length === 2 ? `[${Number(ci[0]).toFixed(4)}, ${Number(ci[1]).toFixed(4)}]` : "not loaded";
    const rerunInterval = rerunCi.length === 2 ? `[${Number(rerunCi[0]).toFixed(4)}, ${Number(rerunCi[1]).toFixed(4)}]` : "not loaded";
    return svg("Calibration arc from descriptive rerun to randomized decision", "A retained descriptive calibration rerun leads to a randomized non-inferiority decision limited to design review; an earlier score is named unavailable rather than recreated.", `
      <rect class="frame" x="12" y="12" width="736" height="336" rx="14"/>
      <text class="micro" x="36" y="42">CALIBRATION ARC / UNCERTAINTY STAYS VISIBLE</text>
      <path class="flow" d="M362 170H402"/>
      <g transform="translate(42 96)"><rect class="node-null" width="286" height="150" rx="8"/><text class="micro" x="16" y="23">EARLIER CALIBRATION</text><text class="label" x="16" y="54">score not retained</text><text class="small" x="16" y="77">no historical rate is reproduced</text><text class="small" x="16" y="104">absence is not a zero</text><text class="micro" x="16" y="128">[NULL] artifact unavailable</text></g>
      <g transform="translate(402 96)"><rect class="node-computed" width="286" height="150" rx="8"/><text class="micro" x="16" y="23">RERUN 2 → RANDOMIZED 2B</text><text class="label" x="16" y="54">${rerun.hits == null ? "?" : rerun.hits} / ${rerun.n == null ? "?" : rerun.n} → ${decision.decision || "NOT LOADED"}</text><text class="small" x="16" y="77">rerun Wilson ${rerunInterval} [C]</text><text class="small" x="16" y="98">2b CPVO ratio ${ratio}; CI ${interval}</text><text class="tag-p" x="16" y="128">[P] design review only</text></g>
      <text class="small" x="368" y="302" text-anchor="middle">The final panel does not arm a policy or activate control.</text>`);
  }

  const rules = [
    ["01", "Instrument first", "measured", "Policy inputs must exist on the ledger before a policy consumes them.", "Input: captured event fields. Status: measurement premise.", "[M] ledger coverage"],
    ["02", "Separate result from model", "decided", "A measured result and a computed extension receive different labels and figures.", "Input: provenance class and formula. Status: adopted editorial rule.", "[P] publication policy"],
    ["03", "Show the cost surface", "proposal", "Cumulative context growth is a scenario to test, not a forecast to sell.", "Input: beta assumption. Status: proposed explorable.", "[C] modeled input"],
    ["04", "Verify independently", "measured", "Agent self-report and independently executed tests are not interchangeable.", "Input: runtime test runner. Status: instrumented signal.", "[M] independent test"],
    ["05", "Route as an arm", "proposal", "A route becomes evidence only when compared under a controlled assignment.", "Input: factor grid. Status: not broadly activated.", "[P] policy proposal"],
    ["06", "Publish nulls", "measured", "Missing LSP coverage and untriggered escalation remain named outcomes.", "Input: coverage and trigger state. Status: current limitation.", "[M] absence state"],
    ["07", "Keep a corpus boundary", "measured", "Historical precursor and current linked-story figures must not be merged.", "Input: manifest identity and date. Status: current receipt.", "[M] corpus identity"],
    ["08", "Change one factor", "proposal", "Campaign adaptation isolates its next uncertainty rather than changing everything at once.", "Input: campaign selection. Status: design practice.", "[P] campaign rule"],
    ["09", "State uncertainty", "decided", "The calibration record carries n and interval before any decision wording.", "Input: registered decision rule. Status: adopted reporting standard.", "[C] decision summary"],
    ["10", "Respect authorization", "decided", "NON-INFERIOR in cap_2b authorizes design review only, not actuation.", "Input: accepted verdict. Status: decided boundary.", "[P] authorization"],
  ];

  function rulesComponent() {
    return rules.map((rule) => {
      const [number, title, status, summary, detail, provenance] = rule;
      const id = `ad-rule-${number}`;
      const badge = {
        measured: ["M", "MEASURED"],
        proposal: ["P", "PROPOSAL"],
        decided: ["C", "DECIDED"],
      }[status];
      return `<article class="ad-rule" data-status="${status}"><button class="ad-rule__toggle" type="button" aria-expanded="false" aria-controls="${id}"><span><span class="ad-rule__number">RULE ${number}</span><span class="ad-rule__status ad-evidence" data-evidence="${badge[0]}">[${badge[0]}] ${badge[1]}</span><span class="ad-rule__title">${title}</span></span><span class="ad-rule__icon" aria-hidden="true">+</span></button><div class="ad-rule__body" id="${id}" hidden><p>${summary}</p><p>${detail}</p><div class="ad-rule__meta">${provenance}</div></div></article>`;
    }).join("");
  }

  function activateRuleCards(root) {
    root.querySelectorAll(".ad-rule__toggle").forEach((button) => {
      button.addEventListener("click", () => {
        const body = document.getElementById(button.getAttribute("aria-controls"));
        const expanded = button.getAttribute("aria-expanded") === "true";
        button.setAttribute("aria-expanded", String(!expanded));
        button.querySelector(".ad-rule__icon").textContent = expanded ? "+" : "-";
        body.hidden = expanded;
      });
    });
  }

  window.AgenticDesign = {
    instrumentCycle,
    nxmProblem,
    planesMap,
    engineModes,
    autonomyEnvelope,
    costCurves,
    escalationChain,
    calibrationArc,
    rulesComponent,
    activateRuleCards,
  };
}());
