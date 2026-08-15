"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.renderPage = renderPage;
exports.renderIndex = renderIndex;
function escapeHtml(value) {
    return value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
function layout(title, body) {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 48rem; margin: 0 auto; padding: 2rem 1rem; line-height: 1.6; }
    a { color: #2563eb; }
    .tags span { background: #e5e7eb; border-radius: 9999px; padding: 0.15rem 0.6rem; font-size: 0.8rem; margin-right: 0.35rem; }
    .meta { color: #6b7280; font-size: 0.9rem; }
  </style>
</head>
<body>
  <p><a href="index.html">&larr; All pages</a></p>
${body}
</body>
</html>
`;
}
function renderPage(page) {
    const metaParts = [];
    if (page.date) {
        metaParts.push(escapeHtml(page.date));
    }
    if (page.tags.length > 0) {
        metaParts.push(`<span class="tags">${page.tags
            .map((t) => `<span>${escapeHtml(t)}</span>`)
            .join('')}</span>`);
    }
    const body = `
  <article>
    <h1>${escapeHtml(page.title)}</h1>
    ${metaParts.length > 0 ? `<p class="meta">${metaParts.join(' · ')}</p>` : ''}
    ${page.contentHtml}
  </article>
`;
    return layout(page.title, body);
}
function renderIndex(pages) {
    const sorted = [...pages].sort((a, b) => a.title.localeCompare(b.title));
    const items = sorted
        .map((page) => {
        const metaParts = [];
        if (page.date) {
            metaParts.push(escapeHtml(page.date));
        }
        if (page.tags.length > 0) {
            metaParts.push(escapeHtml(page.tags.join(', ')));
        }
        const link = `${page.slug}.html`;
        return `    <li>
      <a href="${escapeHtml(link)}">${escapeHtml(page.title)}</a>
      ${metaParts.length > 0 ? `<span class="meta">(${metaParts.join(' · ')})</span>` : ''}
    </li>`;
    })
        .join('\n');
    const body = `
  <h1>All pages</h1>
  <ul>
${items}
  </ul>
`;
    return layout('All pages', body);
}
//# sourceMappingURL=render.js.map