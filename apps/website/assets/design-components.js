/*
 * Agentic Dynamics design components v1.
 *
 * The gallery uses this file as a source of inline SVG, rather than external images,
 * so each diagram remains selectable, accessible, printable, and easy to cite. The
 * functions intentionally contain no data fetching or rendering dependency; pages
 * pass only already-provenanced data.js values into this visual layer. Adapted from
 * references/svg-marker-flow.html, svg-pattern-surface.html, and svg-filter-focus.html.
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

  /**
   * Formats a data-door number without inventing a numeric fallback. A missing
   * publication field stays visibly unavailable, which protects the corpus boundary.
   */
  function count(value) {
    return value == null ? "not loaded" : Number(value).toLocaleString();
  }

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

  // Adapted from references/svg-marker-flow.html and svg-animated-status.html.
  function instrumentCycle(summary) {
    const sessions = count(summary && summary.sessions_total);
    const findings = count(summary && summary.canonical_findings);
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
      <text class="small" x="380" y="180" text-anchor="middle">No policy consumes information that the instrument did not produce.</text>
      <text class="micro" x="380" y="198" text-anchor="middle">CURRENT RECEIPT: ${sessions} sessions [M] / ${findings} findings [M]</text>`);
  }

  // Adapted from references/svg-pattern-surface.html and type-responsive-grid.html.
  function nxmProblem(summary) {
    const sessions = count(summary && summary.sessions_total);
    const findings = count(summary && summary.canonical_findings);
    return svg("N by M evidence surface", "Linked sessions cross independent measurement angles, then analysis creates a second evidence burden.", `
      <rect class="frame" x="12" y="12" width="736" height="336" rx="14"/>
      <text class="micro" x="36" y="42">WHY ONE TASK IS NOT ENOUGH</text>
      <text class="label" x="72" y="86">N linked sessions</text><text class="small" x="72" y="103">Each output becomes the next context.</text>
      <text class="label" x="490" y="86">M measurement angles</text><text class="small" x="490" y="103">Tests alone do not establish durable value.</text>
      <path class="flow" d="M92 132H292"/><path class="flow" d="M92 164H292"/><path class="flow" d="M92 196H292"/>
      <path class="flow-measured" d="M472 118V242"/><path class="flow-measured" d="M548 118V242"/><path class="flow-measured" d="M624 118V242"/>
      <rect x="292" y="118" width="180" height="124" rx="8" fill="url(#ad-hatch)" stroke="#6f7477"/>
      <text class="label" x="382" y="164" text-anchor="middle">N x M evidence</text><text class="tag-c" x="382" y="181" text-anchor="middle">surface [P]</text><text class="small" x="382" y="202" text-anchor="middle">linked work x angles</text>
      <text class="small" x="84" y="131">S1</text><text class="small" x="84" y="163">S2</text><text class="small" x="84" y="195">SN</text><text class="small" x="452" y="112">quality</text><text class="small" x="531" y="112">cost</text><text class="small" x="600" y="112">recovery</text>
      <path class="flow-policy" d="M382 242V282H628"/><text class="label" x="492" y="278" text-anchor="middle">second pass: compare positions and factors</text>
      <text class="micro" x="374" y="320" text-anchor="middle">CURRENT RECEIPT: ${sessions} linked sessions [M] / ${findings} clean findings [M]</text>`);
  }

  // Adapted from references/svg-marker-flow.html and svg-filter-focus.html.
  function planesMap(summary) {
    const variants = count(summary && summary.variants);
    const tierOne = ["experiment", "measurement", "runtime", "adapters", "knowledge", "reporting"];
    const boxes = tierOne.map((name, index) => {
      const x = 42 + index * 116;
      const cls = name === "measurement" ? "node-measured" : "node";
      return `<g transform="translate(${x} 142)"><rect class="${cls}" width="102" height="56" rx="8"/><text class="micro" x="10" y="18">TIER 1</text><text class="label" x="10" y="39">${name}</text></g>`;
    }).join("");
    return svg("Eight planes of Agentic Dynamics", "The eight package planes are arranged as a dependency-aware map. Control is downstream of information-producing planes.", `
      <rect class="frame" x="12" y="12" width="736" height="336" rx="14"/>
       <text class="micro" x="36" y="42">PLATFORM MAP / DEPENDENCY DIRECTION</text>
       <text class="small" x="42" y="72">Arrows point from the importer to its allowed dependency. [P]</text>
       <g transform="translate(302 86)"><rect class="node-policy" width="156" height="34" rx="8"/><text class="micro" x="12" y="14">TIER 2</text><text class="label" x="12" y="28">control</text></g>
       ${boxes}
       <g transform="translate(302 236)"><rect class="node" width="156" height="46" rx="8"/><text class="micro" x="12" y="17">TIER 0</text><text class="label" x="12" y="36">core</text></g>
       <path class="flow-policy" d="M380 120V142"/><path class="flow-measured" d="M380 198V236"/>
       <text class="small" x="42" y="308">Architecture map only [P]. It describes ownership, not system performance.</text>
       <text class="micro" x="42" y="324">CURRENT CORPUS: ${variants} model variants [M], not a plane-performance comparison.</text>`);
  }

  // Adapted from references/svg-marker-flow.html.
  function engineModes(summary) {
    const sessions = count(summary && summary.sessions_total);
    return svg("One engine, two operating modes", "Fixed factors produce one operating cell; varied factors produce a grid, but both run through the same execution engine.", `
      <rect class="frame" x="12" y="12" width="736" height="336" rx="14"/>
      <text class="micro" x="36" y="42">OPERATE OR EXPERIMENT</text>
       <g transform="translate(34 78)"><rect class="node" width="150" height="72" rx="8"/><text class="micro" x="14" y="20">OPERATE</text><text class="label" x="14" y="43">Fixed factors</text><text class="small" x="14" y="59">one selected cell</text></g>
       <g transform="translate(34 204)"><rect class="node-computed" width="150" height="72" rx="8"/><text class="micro" x="14" y="20">EXPERIMENT</text><text class="label" x="14" y="43">Varied factors</text><text class="small" x="14" y="59">controlled grid [C]</text></g>
       <path class="flow" d="M184 114H224M184 240H224"/>
       <g transform="translate(224 140)"><rect class="node-measured" width="88" height="72" rx="8"/><text class="label" x="44" y="34" text-anchor="middle">CELL</text><text class="small" x="44" y="52" text-anchor="middle">unit</text></g>
       <path class="flow-measured" d="M312 176H346M426 176H460M540 176H574"/>
       <g transform="translate(346 140)"><rect class="node" width="80" height="72" rx="8"/><text class="label" x="40" y="34" text-anchor="middle">COMPILE</text><text class="small" x="40" y="52" text-anchor="middle">jobs</text></g>
       <g transform="translate(460 140)"><rect class="node-measured" width="80" height="72" rx="8"/><text class="label" x="40" y="34" text-anchor="middle">ATTEMPTS</text><text class="small" x="40" y="52" text-anchor="middle">events</text></g>
       <g transform="translate(574 140)"><rect class="node" width="100" height="72" rx="8"/><text class="label" x="50" y="34" text-anchor="middle">LEDGER</text><text class="small" x="50" y="52" text-anchor="middle">record</text></g>
       <path class="flow-policy" d="M109 276V304H574"/><text class="tag-p" x="344" y="296">only the grid: compare arms -> adapt</text>
       <text class="micro" x="42" y="314">CURRENT RECEIPT: ${sessions} captured sessions [M]; count does not alter this architecture [P].</text>`);
  }

  // Adapted from references/svg-pattern-surface.html and svg-filter-focus.html.
  function autonomyEnvelope(summary) {
    const findings = count(summary && summary.canonical_findings);
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
       <path class="flow" d="M548 206V248H400"/><path class="flow-policy" d="M548 206V248H552"/><path class="flow-policy" d="M548 206V248H654"/>
       <text class="label" x="400" y="266" text-anchor="middle">reject / rework</text><text class="label" x="552" y="266" text-anchor="middle">accept</text><text class="label" x="654" y="266" text-anchor="middle">halt / escalate</text>
       <text class="small" x="66" y="318">Typed checkpoints are not-run instrumentation, not an implied capability. [NULL]</text>
       <text class="micro" x="66" y="334">CURRENT RECEIPT: ${findings} clean findings [M]; no authorization is inferred.</text>`);
  }

  // Adapted from references/d3-line-arc.html and d3-interactive-curve.html.
  function costCurves(designParameters) {
    const beta = designParameters && designParameters.beta ? designParameters.beta.value : null;
    const betaLabel = beta == null ? "not loaded" : Number(beta).toFixed(4);
    const numericBeta = Number(beta);
    // The curve is re-derived from the displayed formula on each range input, so
    // the visual movement represents only the declared [P] beta assumption.
    const curvePath = Number.isFinite(numericBeta) ? (() => {
      const maximumN = 100;
      const scenarioCost = (n) => n + numericBeta * n * (n - 1) / 2;
      const maximumCost = scenarioCost(maximumN);
      return Array.from({ length: 6 }, (_, index) => {
        const n = index * maximumN / 5;
        const x = 42 + (204 * index / 5);
        const y = 145 - (109 * scenarioCost(n) / maximumCost);
        return `${index ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`;
      }).join(" ");
    })() : "M42 145";
    return svg("Observed and modeled cost curves are separate", "The current corpus has no canonical story-arc lab output, while the cumulative curve is explicitly modeled from a beta assumption.", `
      <rect class="frame" x="12" y="12" width="736" height="336" rx="14"/>
      <text class="micro" x="36" y="42">COST SURFACES / DO NOT MERGE EVIDENCE CLASSES</text>
      <g transform="translate(50 78)"><rect class="node-null" width="286" height="188" rx="8"/><text class="label" x="18" y="30">Immediate story arc</text><text class="small" x="18" y="49">Current canonical lab output is absent.</text><path class="guide-dash" d="M38 150H248M38 150V72"/><text class="small" x="143" y="115" text-anchor="middle">not measured</text><text class="micro" x="18" y="172">[NULL] no published series</text></g>
       <g transform="translate(424 78)"><rect class="node-computed" width="286" height="188" rx="8"/><text class="label" x="18" y="30">Cumulative scenario</text><text class="small" x="18" y="49">C(N) = N + beta*N(N-1)/2</text><path class="guide" d="M38 150H248M38 150V72"/><path class="curve-computed" d="${curvePath}"/><text class="tag-c" x="158" y="77">[C] beta = ${betaLabel}, an input</text><text class="small" x="18" y="172">model, not forecast</text></g>
      <text class="small" x="380" y="308" text-anchor="middle">A displayed curve must say whether it is observed, computed, or unavailable.</text>`);
  }

  // Adapted from references/svg-marker-flow.html and svg-pattern-surface.html.
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

  // Adapted from references/scroll-sticky-overlay.html and d3-line-arc.html.
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
    const armRate = (arm) => arm.accepted_outcomes == null || arm.n == null
      ? "not loaded"
      : `${arm.accepted_outcomes} / ${arm.n}`;
    return svg("Calibration arc from descriptive rerun to randomized decision", "A retained descriptive calibration rerun leads to a randomized non-inferiority decision limited to design review; an earlier score is named unavailable rather than recreated.", `
      <rect class="frame" x="12" y="12" width="736" height="336" rx="14"/>
      <text class="micro" x="36" y="42">CALIBRATION ARC / UNCERTAINTY STAYS VISIBLE</text>
      <path class="flow" d="M250 170H278M490 170H518"/>
      <g transform="translate(34 96)"><rect class="node-null" width="216" height="150" rx="8"/><text class="micro" x="14" y="23">EARLIER CALIBRATION</text><text class="label" x="14" y="54">score not retained</text><text class="small" x="14" y="77">no historical rate reproduced</text><text class="small" x="14" y="100">absence is not a zero</text><text class="micro" x="14" y="128">[NULL] artifact unavailable</text></g>
      <g transform="translate(278 96)"><rect class="node-measured" width="212" height="150" rx="8"/><text class="micro" x="14" y="23">DESCRIPTIVE RERUN</text><text class="label" x="14" y="54">${rerun.hits == null ? "?" : rerun.hits} / ${rerun.n == null ? "?" : rerun.n} hits [M]</text><text class="small" x="14" y="77">Wilson ${rerunInterval} [C]</text><text class="small" x="14" y="100">descriptive only</text><text class="tag-m" x="14" y="128">n remains visible</text></g>
      <g transform="translate(518 96)"><rect class="node-computed" width="184" height="150" rx="8"/><text class="micro" x="14" y="23">RANDOMIZED 2B</text><text class="label" x="14" y="52">${decision.decision || "NOT LOADED"} [C]</text><text class="small" x="14" y="76">static ${armRate(staticArm)} [M]</text><text class="small" x="14" y="96">adaptive ${armRate(adaptiveArm)} [M]</text><text class="small" x="14" y="116">ratio ${ratio}; ${interval} [C]</text><text class="tag-p" x="14" y="134">design review only [P]</text></g>
      <text class="small" x="368" y="302" text-anchor="middle">The final panel does not arm a policy or activate control.</text>`);
  }

  const rules = [
    ["01", "Instrument first", "instrumented", "Policy inputs must exist on the ledger before a policy consumes them.", "captured event fields", "[M] ledger coverage", "experiment_spec.py ledger contract", "coverage is not universal evidence", "extend ledger coverage before a new policy arm"],
    ["02", "Separate result from model", "decided", "A measured result and a computed extension receive different labels and figures.", "provenance class and formula", "[P] publication policy", "cap_site_revamp_research.md", "an editorial rule cannot validate an outcome", "audit new figures for tag and denominator"],
    ["03", "Show the cost surface", "proposal", "Cumulative context growth is a scenario to test, not a forecast to sell.", "beta assumption", "[C] modeled input", "design_parameters.beta", "no canonical immediate story arc is published", "measure a canonical story-cost series"],
    ["04", "Verify independently", "instrumented", "Agent self-report and independently executed tests are not interchangeable.", "runtime test runner", "[M] independent test", "runtime.test_runner", "a suite can be absent or incomplete", "capture test execution coverage per attempt"],
    ["05", "Route as an arm", "proposal", "A route becomes evidence only when compared under a controlled assignment.", "factor grid", "[P] policy proposal", "experiment_spec.py factor design", "no broadly activated routing claim", "run a controlled routing comparison"],
    ["06", "Publish nulls", "instrumented", "Missing LSP coverage and untriggered escalation remain named outcomes.", "coverage and trigger state", "[M] absence state", "campaigns.session_routing", "an untriggered arm does not estimate its premium", "create a triggered escalation campaign"],
    ["07", "Keep a corpus boundary", "instrumented", "Historical precursor and current linked-story figures must not be merged.", "manifest identity and date", "[M] corpus identity", "data.js summary and manifest", "corpus differences constrain comparison", "publish a bridge study only with a declared join"],
    ["08", "Change one factor", "proposal", "Campaign adaptation isolates its next uncertainty rather than changing everything at once.", "campaign selection", "[P] campaign rule", "ExperimentSpec adapt contract", "one-factor change may be slower", "select the next uncertainty explicitly"],
    ["09", "State uncertainty", "decided", "The calibration record carries n and interval before any decision wording.", "registered decision rule", "[C] decision summary", "campaigns.calibration and cap_2b", "the calibration rerun is descriptive", "replicate the randomized comparison"],
    ["10", "Respect authorization", "decided", "A campaign decision authorizes design review only, not actuation.", "accepted verdict and authorization", "[P] authorization", "campaigns.cap_2b", "the decision does not arm control", "record a separate actuation authorization"],
  ];

  // Adapted from references/card-details.html and card-tooltip-badge.html.
  function rulesComponent(campaigns, summary, generatedAt) {
    // Campaign-derived cards can only be decided when the current data door says
    // so. The remaining cards describe instrumented premises or proposals, not
    // fabricated measurements of a policy outcome.
    const cap2b = campaigns && campaigns.cap_2b ? campaigns.cap_2b : {};
    const escalation = campaigns && campaigns.escalation ? campaigns.escalation : {};
    const decision = cap2b.decision_rule ? cap2b.decision_rule.decision : "not loaded";
    const decisionStatus = cap2b.status === "DECIDED" ? "decided" : "proposal";
    const corpusInstrumented = summary && summary.sessions_total != null;
    const escalationMeasured = escalation.status === "MEASURED";
    const updated = generatedAt ? String(generatedAt).slice(0, 10) : "not loaded";
    return rules.map((rule) => {
      const [number, title, declaredStatus, summary, inputs, provenance, source, limitation, nextTest] = rule;
      const status = ["09", "10"].includes(number)
        ? decisionStatus
        : ["01", "04", "07"].includes(number) && !corpusInstrumented
          ? "proposal"
          : number === "06" && !escalationMeasured
            ? "proposal"
            : declaredStatus;
      const id = `ad-rule-${number}`;
      const statusLabel = {
        instrumented: "INSTRUMENTED",
        proposal: "PROPOSAL",
        decided: "DECIDED",
      }[status];
      const evidenceClass = provenance.slice(1, 2);
      const decisionDetail = ["09", "10"].includes(number) ? ` Current campaign decision: ${decision} [C].` : "";
      return `<article class="ad-rule" data-status="${status}"><button class="ad-rule__toggle" type="button" aria-expanded="false" aria-controls="${id}"><span><span class="ad-rule__number">RULE ${number}</span><span class="ad-rule__status ad-evidence" data-evidence="${evidenceClass}">[${evidenceClass}] ${statusLabel}</span><span class="ad-rule__title">${title}</span></span><span class="ad-rule__icon" aria-hidden="true">+</span></button><div class="ad-rule__body" id="${id}" hidden><p>${summary}</p><p><strong>Inputs:</strong> ${inputs}.${decisionDetail}</p><p><strong>Limitation:</strong> ${limitation} <strong>Next test:</strong> ${nextTest}.</p><div class="ad-rule__meta">${provenance} | Source: ${source} | Updated: ${updated}</div></div></article>`;
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
