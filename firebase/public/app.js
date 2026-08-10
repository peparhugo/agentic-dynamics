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

/* --- Page Table of Contents (auto-generated from headings) --- */
(function() {
  var toc = document.getElementById('page-toc');
  if (!toc) return;
  document.body.classList.add('has-toc');

  var header = document.createElement('div');
  header.className = 'page-toc-header';
  header.textContent = 'On this page';
  toc.appendChild(header);

  // Collect h2 and h3 with content
  var headings = document.querySelectorAll('h2, h3');
  var tocItems = [];
  headings.forEach(function(h) {
    var text = h.textContent.trim();
    if (!text || text.length < 2) return;
    // Generate id if missing
    if (!h.id) {
      h.id = text.toLowerCase()
        .replace(/[^a-z0-9\u00d7\s-]+/g, '')
        .replace(/\s+/g, '-')
        .replace(/-+/g, '-')
        .replace(/^-|-$/g, '');
    }
    tocItems.push({ tag: h.tagName, id: h.id, text: text });
  });

  if (tocItems.length === 0) { toc.style.display = 'none'; return; }

  var html = '';
  tocItems.forEach(function(item) {
    var cls = item.tagName === 'H3' ? ' toc-h3' : (item.tagName === 'H4' ? ' toc-h4' : '');
    var displayText = item.text;
    if (displayText.length > 28) {
      var cut = displayText.lastIndexOf(' ', 28);
      if (cut < 20) cut = 28;
      displayText = displayText.substring(0, cut) + '\u2026';
    }
    html += '<a href="#' + item.id + '" class="toc-link' + cls + '" data-target="' + item.id + '" title="' + item.text.replace(/"/g, '&quot;') + '">' + displayText + '</a>';
  });
  toc.innerHTML = html;

  // Highlight current section on scroll
  var links = toc.querySelectorAll('.toc-link');
  if (links.length === 0) return;

  var scrollHandler = function() {
    var viewportMid = window.innerHeight * 0.3;
    var activeFound = false;
    for (var i = links.length - 1; i >= 0; i--) {
      var target = document.getElementById(links[i].dataset.target);
      if (!target) continue;
      var rect = target.getBoundingClientRect();
      if (rect.top <= viewportMid) {
        if (!activeFound) {
          links[i].classList.add('active');
          if (links[i].offsetTop > toc.scrollTop + toc.clientHeight - 40 || links[i].offsetTop < toc.scrollTop) {
            toc.scrollTop = links[i].offsetTop - toc.clientHeight / 3;
          }
          activeFound = true;
        } else {
          links[i].classList.remove('active');
        }
      } else {
        links[i].classList.remove('active');
      }
    }
  };

  window.addEventListener('scroll', scrollHandler, { passive: true });
  scrollHandler(); // initial highlight
})();
