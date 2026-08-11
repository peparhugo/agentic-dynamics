"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.pageTemplate = pageTemplate;
exports.indexTemplate = indexTemplate;
function pageTemplate(page) {
    const tagList = page.tags && page.tags.length > 0
        ? page.tags.map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join(' ')
        : '';
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(page.title)}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 720px; margin: 0 auto; padding: 2rem; line-height: 1.6; color: #222; }
    .tag { display: inline-block; background: #e2e8f0; padding: 0.1rem 0.5rem; border-radius: 4px; font-size: 0.85rem; margin-right: 0.25rem; }
    .date { color: #666; font-size: 0.9rem; }
    nav { margin-bottom: 2rem; }
    nav a { color: #1a56db; }
    h1 { margin-bottom: 0.25rem; }
  </style>
</head>
<body>
  <nav><a href="index.html">&larr; Home</a></nav>
  <h1>${escapeHtml(page.title)}</h1>
  ${page.date ? `<p class="date">${escapeHtml(page.date)}</p>` : ''}
  ${tagList ? `<p>${tagList}</p>` : ''}
  <hr>
  ${page.html}
</body>
</html>`;
}
function indexTemplate(pages) {
    const items = pages
        .map((p) => `<li><a href="${escapeHtml(p.slug)}.html">${escapeHtml(p.title)}</a>${p.date ? ` <span class="date">— ${escapeHtml(p.date)}</span>` : ''}</li>`)
        .join('\n      ');
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Index</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 720px; margin: 0 auto; padding: 2rem; line-height: 1.6; color: #222; }
    .date { color: #666; font-size: 0.9rem; }
    h1 { margin-bottom: 0.5rem; }
    ul { padding-left: 1.2rem; }
    li { margin-bottom: 0.25rem; }
  </style>
</head>
<body>
  <h1>All Pages</h1>
  <ul>
      ${items}
  </ul>
  ${pages.length === 0 ? '<p>No pages found.</p>' : ''}
</body>
</html>`;
}
function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
//# sourceMappingURL=template.js.map