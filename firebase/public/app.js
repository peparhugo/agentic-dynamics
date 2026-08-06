/* === AI FinOps Framework — Shared JavaScript === */
/* v0.2 */

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
