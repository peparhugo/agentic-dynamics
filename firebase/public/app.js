/* === AI FinOps Framework — Shared JavaScript === */
/* v0.4 */

/* --- Theme Toggle --- */
(function() {
  const saved = localStorage.getItem('ai-finops-theme');
  if (saved === 'light') document.body.classList.add('light');

  const toggle = document.createElement('button');
  toggle.className = 'theme-toggle';
  toggle.setAttribute('aria-label', 'Toggle light/dark mode');
  toggle.textContent = document.body.classList.contains('light') ? '☀' : '☾';
  toggle.addEventListener('click', function() {
    document.body.classList.toggle('light');
    const isLight = document.body.classList.contains('light');
    toggle.textContent = isLight ? '☀' : '☾';
    localStorage.setItem('ai-finops-theme', isLight ? 'light' : 'dark');
  });
  document.body.appendChild(toggle);
})();

/* --- Data-driven injection (reads window.FRAMEWORK_DATA from data.js) --- */
(function() {
  document.addEventListener('DOMContentLoaded', function() {
    var D = window.FRAMEWORK_DATA;
    if (!D) return;

    function fmtUSD(v) { return (typeof v === 'number' ? v.toFixed(2) : v); }

    function findModel(D, idPart) {
      var ms = D.models || [];
      for (var mi = 0; mi < ms.length; mi++) {
        if (ms[mi].id.indexOf(idPart) >= 0) return ms[mi];
      }
      return {};
    }

    var statMap = {
      'sessions': function() { return D.summary.sessions_total; },
      'worktrees': function() { return D.summary.worktrees_total; },
      'reports': function() { return D.summary.game_reports; },
      'cost': function() { return fmtUSD(D.summary.total_cost); },
      'architectures': function() { return D.summary.architectures; },
      'variants': function() { return D.summary.variants; },
      'costgap': function() { return D.derived.cost_gap; },
      'passrate': function() { return D.derived.overall_pass_rate; },
      'deepseek_cost': function() { return fmtUSD(D.derived.total_cost_deepseek); },
      'claude_cost': function() { return fmtUSD(D.derived.total_cost_claude); },
      'total_tests': function() { return D.derived.total_tests_passed + '/' + D.derived.total_tests_run; },
      'woc': function() { return D.calculator.woc_ratio.toFixed(2); },
      'woc_percent': function() { return Math.round(D.calculator.woc_ratio * 100) + '%'; },
      'deepseek_cost_per': function() { return fmtUSD(findModel(D, 'deepseek').avg_cost); },
      'claude_cost_per': function() { return fmtUSD(findModel(D, 'claude').avg_cost); },
      'gpt56_cost_per': function() { return fmtUSD(findModel(D, 'gpt-5.6').avg_cost); },
      'deepseek_narration': function() { var m = findModel(D, 'deepseek'); return (m.narration_rate || 0) + '%'; },
      'claude_narration': function() { var m = findModel(D, 'claude'); return (m.narration_rate || 0) + '%'; },
      'nano_narration': function() { var m = findModel(D, 'nano'); return (m.narration_rate || 0) + '%'; },
      'deepseek_penalty': function() { return ((findModel(D, 'deepseek').avg_narration_penalty || 0) * 100).toFixed(1) + '%'; },
      'claude_penalty': function() { return ((findModel(D, 'claude').avg_narration_penalty || 0) * 100).toFixed(1) + '%'; },
    };

    var els = document.querySelectorAll('[data-stat]');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      var key = el.getAttribute('data-stat');
      var fn = statMap[key];
      if (fn) {
        var val = fn();
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
          el.value = val;
        } else {
          el.textContent = val;
        }
      }
    }

    var fmtEls = document.querySelectorAll('[data-stat-fmt]');
    for (var j = 0; j < fmtEls.length; j++) {
      var fel = fmtEls[j];
      var fkey = fel.getAttribute('data-stat-fmt');
      var ffn = statMap[fkey];
      if (ffn) fel.textContent = ffn();
    }
  });
})();
