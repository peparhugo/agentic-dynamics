WIDGET_JS = r"""
(function () {
  'use strict';

  var CONF = {
    apiBase: '/api',
    debounceMs: 150,
    minChars: 1,
    maxResults: 8,
    cacheMs: 60000,
    maxRecent: 5,
  };

  function debounce(fn, ms) {
    var timer;
    return function () {
      var ctx = this, args = arguments;
      clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }

  var ResultsCache = function () {
    this._store = {};
  };
  ResultsCache.prototype.get = function (key) {
    var e = this._store[key];
    if (!e) return null;
    if (Date.now() > e.expiry) { delete this._store[key]; return null; }
    return e.data;
  };
  ResultsCache.prototype.set = function (key, data, ttl) {
    this._store[key] = { data: data, expiry: Date.now() + (ttl || CONF.cacheMs) };
  };
  ResultsCache.prototype.clear = function () { this._store = {}; };

  function escapeHtml(str) {
    var map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    return str.replace(/[&<>"']/g, function (m) { return map[m]; });
  }

  function highlightText(text, query) {
    if (!query) return escapeHtml(text);
    var escaped = escapeHtml(text);
    var q = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    var re = new RegExp('(' + q + ')', 'gi');
    return escaped.replace(re, '<mark>$1</mark>');
  }

  function track(apiBase, type, data) {
    try {
      var xhr = new XMLHttpRequest();
      xhr.open('POST', apiBase + '/analytics', true);
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(JSON.stringify({ type: type, data: data }));
    } catch (_) {}
  }

  var AutocompleteSearch = function (input) {
    this.input = input;
    this.apiBase = input.getAttribute('data-api-base') || CONF.apiBase;
    this.cache = new ResultsCache();
    this.state = { query: '', results: null, selectedIndex: -1, isLoading: false, isOpen: false, hasError: false };
    this.abortController = null;
    this.debouncedFetch = debounce(this._fetch.bind(this), CONF.debounceMs);
    this._buildDom();
    this._bindEvents();
    this.track('widget_load', {});
  };

  AutocompleteSearch.prototype._buildDom = function () {
    var self = this;
    var wrap = document.createElement('div');
    wrap.className = 'ac-wrap';
    this.input.parentNode.insertBefore(wrap, this.input);
    wrap.appendChild(this.input);
    this.wrap = wrap;

    var dd = document.createElement('div');
    dd.className = 'ac-dropdown';
    dd.setAttribute('role', 'listbox');
    dd.id = 'ac-listbox-' + Math.random().toString(36).slice(2, 9);
    dd.setAttribute('aria-label', 'Search suggestions');
    wrap.appendChild(dd);
    this.dropdown = dd;

    this.input.setAttribute('role', 'combobox');
    this.input.setAttribute('aria-expanded', 'false');
    this.input.setAttribute('aria-owns', dd.id);
    this.input.setAttribute('aria-autocomplete', 'list');
    this.input.setAttribute('autocomplete', 'off');
    this.input.setAttribute('aria-haspopup', 'listbox');

    this.listboxId = dd.id;
  };

  AutocompleteSearch.prototype._bindEvents = function () {
    var self = this;
    this.input.addEventListener('input', function () {
      self._onInput();
    });
    this.input.addEventListener('focus', function () {
      self._onFocus();
    });
    this.input.addEventListener('keydown', function (e) {
      self._onKeyDown(e);
    });
    this.input.addEventListener('blur', function () {
      setTimeout(function () { self._close(); }, 150);
    });
    this.dropdown.addEventListener('mousedown', function (e) {
      e.preventDefault();
      var option = e.target.closest('[role="option"]');
      if (option) self._selectByElement(option);
    });
  };

  AutocompleteSearch.prototype._onInput = function () {
    var q = this.input.value.trim();
    if (q.length < CONF.minChars) {
      this._showRecent();
      return;
    }
    this.state.query = q;
    this.state.isLoading = true;
    this.state.hasError = false;
    this.state.results = null;
    this._open();
    this._render();
    this.debouncedFetch(q);
    this.track('search_start', { query: q });
  };

  AutocompleteSearch.prototype._onFocus = function () {
    if (!this.state.isOpen && this.input.value.trim().length < CONF.minChars) {
      this._showRecent();
    }
  };

  AutocompleteSearch.prototype._fetch = function (query) {
    var self = this;
    var cacheKey = query.toLowerCase();
    var cached = this.cache.get(cacheKey);
    if (cached) {
      this.state.results = cached;
      this.state.isLoading = false;
      this.state.selectedIndex = -1;
      this._render();
      this.track('search_complete', { query: query, source: 'cache', total: cached.total });
      return;
    }

    if (this.abortController) this.abortController.abort();
    this.abortController = new AbortController();

    fetch(this.apiBase + '/suggest?q=' + encodeURIComponent(query), {
      signal: this.abortController.signal,
    })
      .then(function (r) {
        if (!r.ok) throw new Error('Network error ' + r.status);
        return r.json();
      })
      .then(function (data) {
        if (self.state.query !== query) return;
        self.cache.set(cacheKey, data);
        self.state.results = data;
        self.state.isLoading = false;
        self.state.hasError = false;
        self.state.selectedIndex = -1;
        self._render();
        self.track('search_complete', { query: query, source: 'network', total: data.total });
      })
      .catch(function (err) {
        if (err.name === 'AbortError') return;
        if (self.state.query !== query) return;
        self.state.isLoading = false;
        self.state.hasError = true;
        self.state.results = null;
        self._render();
        self.track('search_error', { query: query, error: err.message });
      });
  };

  AutocompleteSearch.prototype._showRecent = function () {
    this.state.query = '';
    this.state.isLoading = false;
    this.state.hasError = false;
    this.state.selectedIndex = -1;
    var recents = this._getRecentSearches();
    if (recents.length === 0) {
      this.state.results = null;
      this._close();
      this._render();
      return;
    }
    this.state.results = {
      query: '',
      groups: [{ category: 'Recent Searches', results: recents.map(function (r, i) {
        return { id: 'recent-' + i, title: r, description: '', category: 'Recent Searches', url: '', score: 0 };
      })}],
      total: recents.length,
    };
    this._open();
    this._render();
  };

  AutocompleteSearch.prototype._open = function () {
    if (this.state.isOpen) return;
    this.state.isOpen = true;
    this.dropdown.style.display = '';
    this.input.setAttribute('aria-expanded', 'true');
    this.wrap.classList.add('ac-open');
  };

  AutocompleteSearch.prototype._close = function () {
    if (!this.state.isOpen) return;
    this.state.isOpen = false;
    this.dropdown.style.display = 'none';
    this.input.setAttribute('aria-expanded', 'false');
    this.input.removeAttribute('aria-activedescendant');
    this.wrap.classList.remove('ac-open');
    this.state.selectedIndex = -1;
  };

  AutocompleteSearch.prototype._render = function () {
    var dd = this.dropdown;
    if (!this.state.isOpen) { dd.innerHTML = ''; return; }

    if (this.state.isLoading) {
      dd.innerHTML = '<div class="ac-state ac-loading" role="status"><span class="ac-spinner"></span> Searching...</div>';
      return;
    }

    if (this.state.hasError) {
      dd.innerHTML = '<div class="ac-state ac-error" role="alert">Something went wrong. <button type="button" class="ac-retry">Retry</button></div>';
      var self = this;
      dd.querySelector('.ac-retry').addEventListener('click', function () { self._onInput(); });
      return;
    }

    var groups = this.state.results && this.state.results.groups;
    if (!groups || this.state.results.total === 0) {
      dd.innerHTML = '<div class="ac-state ac-empty">No results found for "<strong>' + escapeHtml(this.state.query) + '</strong>"</div>';
      return;
    }

    var html = '';
    var optionIdx = 0;
    var self = this;

    groups.forEach(function (group) {
      html += '<div class="ac-group" role="group" aria-label="' + escapeHtml(group.category) + '">';
      html += '<div class="ac-group-label" aria-hidden="true">' + escapeHtml(group.category) + '</div>';
      group.results.forEach(function (item) {
        var cls = 'ac-option';
        if (optionIdx === self.state.selectedIndex) cls += ' ac-active';
        html += '<div role="option" id="ac-opt-' + optionIdx
          + '" class="' + cls + '" data-idx="' + optionIdx + '" aria-selected="' + (optionIdx === self.state.selectedIndex ? 'true' : 'false') + '">';
        html += '<span class="ac-option-title">' + highlightText(item.title, self.state.query) + '</span>';
        if (item.description) {
          html += '<span class="ac-option-desc">' + escapeHtml(item.description) + '</span>';
        }
        html += '</div>';
        optionIdx++;
      });
      html += '</div>';
    });

    dd.innerHTML = html;

    if (self.state.selectedIndex >= 0) {
      var activeEl = dd.querySelector('[data-idx="' + self.state.selectedIndex + '"]');
      if (activeEl) {
        activeEl.scrollIntoView({ block: 'nearest' });
        self.input.setAttribute('aria-activedescendant', 'ac-opt-' + self.state.selectedIndex);
      }
    } else {
      self.input.removeAttribute('aria-activedescendant');
    }
  };

  AutocompleteSearch.prototype._getOptionCount = function () {
    if (!this.state.results || !this.state.results.groups) return 0;
    var n = 0;
    this.state.results.groups.forEach(function (g) { n += g.results.length; });
    return n;
  };

  AutocompleteSearch.prototype._getOptionByIdx = function (idx) {
    var n = 0;
    if (!this.state.results || !this.state.results.groups) return null;
    for (var i = 0; i < this.state.results.groups.length; i++) {
      var g = this.state.results.groups[i];
      if (idx < n + g.results.length) {
        return g.results[idx - n];
      }
      n += g.results.length;
    }
    return null;
  };

  AutocompleteSearch.prototype._onKeyDown = function (e) {
    if (!this.state.isOpen) return;
    var key = e.key;
    var total = this._getOptionCount();

    if (key === 'ArrowDown') {
      e.preventDefault();
      this.state.selectedIndex = Math.min(this.state.selectedIndex + 1, total - 1);
      if (this.state.selectedIndex >= total) this.state.selectedIndex = 0;
      this._render();
    } else if (key === 'ArrowUp') {
      e.preventDefault();
      this.state.selectedIndex = Math.max(this.state.selectedIndex - 1, 0);
      if (this.state.selectedIndex < 0) this.state.selectedIndex = total - 1;
      this._render();
    } else if (key === 'Enter') {
      e.preventDefault();
      if (this.state.selectedIndex >= 0) {
        this._selectCurrent();
      } else {
        this._submitSearch();
      }
    } else if (key === 'Escape') {
      e.preventDefault();
      this._close();
      this.input.blur();
    }
  };

  AutocompleteSearch.prototype._selectByElement = function (el) {
    var idx = parseInt(el.getAttribute('data-idx'), 10);
    var item = this._getOptionByIdx(idx);
    if (!item) return;
    this.state.selectedIndex = idx;
    this._selectResult(item);
  };

  AutocompleteSearch.prototype._selectCurrent = function () {
    var item = this._getOptionByIdx(this.state.selectedIndex);
    if (item) this._selectResult(item);
  };

  AutocompleteSearch.prototype._selectResult = function (item) {
    this.input.value = item.title;
    this._saveRecentSearch(item.title);
    this.track('search_select', {
      query: this.state.query,
      resultId: item.id,
      resultTitle: item.title,
      resultCategory: item.category,
      index: this.state.selectedIndex,
    });
    this._close();
    if (item.url) {
      window.location.href = item.url;
    } else {
      this.input.form && this.input.form.submit();
    }
  };

  AutocompleteSearch.prototype._submitSearch = function () {
    var q = this.input.value.trim();
    if (!q) return;
    this._saveRecentSearch(q);
    this.track('search_submit', { query: q });
    this._close();
    if (this.input.form) this.input.form.submit();
  };

  AutocompleteSearch.prototype._saveRecentSearch = function (q) {
    try {
      var recents = this._getRecentSearches();
      var idx = recents.indexOf(q);
      if (idx >= 0) recents.splice(idx, 1);
      recents.unshift(q);
      if (recents.length > CONF.maxRecent) recents.pop();
      localStorage.setItem('ac-recent-searches', JSON.stringify(recents));
    } catch (_) {}
  };

  AutocompleteSearch.prototype._getRecentSearches = function () {
    try {
      return JSON.parse(localStorage.getItem('ac-recent-searches') || '[]');
    } catch (_) { return []; }
  };

  AutocompleteSearch.prototype.track = function (type, data) {
    track(this.apiBase, type, data);
  };

  function autoInit() {
    var inputs = document.querySelectorAll('input[data-autocomplete]');
    for (var i = 0; i < inputs.length; i++) {
      new AutocompleteSearch(inputs[i]);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', autoInit);
  } else {
    autoInit();
  }

  window.AutocompleteSearch = AutocompleteSearch;
})();
"""

DEMO_PAGE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Autocomplete Search Demo</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f5f5f7;
  min-height: 100vh;
  display: flex;
  justify-content: center;
  padding-top: 80px;
}

.demo-container {
  width: 100%;
  max-width: 540px;
  padding: 0 16px;
}

.demo-title {
  font-size: 28px;
  font-weight: 700;
  color: #1d1d1f;
  margin-bottom: 24px;
  text-align: center;
}

.ac-wrap {
  position: relative;
  width: 100%;
}

.ac-wrap input {
  width: 100%;
  height: 48px;
  padding: 0 16px 0 44px;
  font-size: 16px;
  border: 2px solid #d2d2d7;
  border-radius: 12px;
  background: #fff;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  color: #1d1d1f;
}

.ac-wrap input::placeholder { color: #86868b; }

.ac-wrap input:focus {
  border-color: #0071e3;
  box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.15);
}

.ac-wrap.ac-open input {
  border-radius: 12px 12px 0 0;
  border-bottom-color: transparent;
}

.ac-wrap::before {
  content: '';
  position: absolute;
  left: 16px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2386868b' stroke-width='2'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cpath d='M21 21l-4.35-4.35'/%3E%3C/svg%3E") center/contain no-repeat;
  z-index: 1;
  pointer-events: none;
}

.ac-dropdown {
  display: none;
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: #fff;
  border: 2px solid #0071e3;
  border-top: 1px solid #e5e5ea;
  border-radius: 0 0 12px 12px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.12);
  max-height: 420px;
  overflow-y: auto;
  z-index: 1000;
  padding: 4px 0;
}

.ac-group-label {
  padding: 8px 16px 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #86868b;
}

.ac-group:first-child .ac-group-label { padding-top: 4px; }

.ac-option {
  display: flex;
  flex-direction: column;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.1s;
  border-left: 3px solid transparent;
}

.ac-option:hover,
.ac-option.ac-active {
  background: #f0f0f5;
  border-left-color: #0071e3;
}

.ac-option-title {
  font-size: 15px;
  font-weight: 500;
  color: #1d1d1f;
  line-height: 1.4;
}

.ac-option-desc {
  font-size: 12px;
  color: #86868b;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ac-option mark {
  background: #fff3bf;
  color: inherit;
  border-radius: 2px;
  padding: 0 1px;
  font-weight: 600;
}

.ac-state {
  padding: 20px 16px;
  text-align: center;
  color: #86868b;
  font-size: 14px;
}

.ac-loading { display: flex; align-items: center; justify-content: center; gap: 8px; }

.ac-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid #e5e5ea;
  border-top-color: #0071e3;
  border-radius: 50%;
  animation: ac-spin 0.6s linear infinite;
}

@keyframes ac-spin { to { transform: rotate(360deg); } }

.ac-error { color: #d32f2f; }
.ac-retry {
  background: none;
  border: none;
  color: #0071e3;
  cursor: pointer;
  font-size: 14px;
  text-decoration: underline;
  padding: 0;
  margin-left: 4px;
}
.ac-retry:hover { color: #005bb5; }

.ac-empty strong { color: #1d1d1f; }

@media (max-width: 767px) {
  body { padding-top: 16px; }
  .demo-container { padding: 0; }
  .demo-title { font-size: 22px; margin-bottom: 16px; }
  .ac-wrap input {
    border-radius: 0;
    height: 52px;
    font-size: 16px;
    border-left: none;
    border-right: none;
  }
  .ac-wrap.ac-open input { border-radius: 0; }
  .ac-dropdown {
    position: fixed;
    top: 52px;
    left: 0;
    right: 0;
    bottom: 0;
    max-height: none;
    border-radius: 0;
    border-left: none;
    border-right: none;
    overflow-y: auto;
    z-index: 999;
  }
}
</style>
</head>
<body>
<div class="demo-container">
  <h1 class="demo-title">Search</h1>
  <form onsubmit="return false">
    <input type="text" data-autocomplete data-api-base="/api" placeholder="Search products, guides, people..." aria-label="Search">
  </form>
</div>
<script src="/widget/autocomplete.js"></script>
</body>
</html>
"""
