"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.escapeHtml = escapeHtml;
exports.renderPage = renderPage;
exports.renderIndex = renderIndex;
function escapeHtml(input) {
    return input
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
function formatTags(tags) {
    if (tags.length === 0)
        return '';
    const items = tags.map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join(' ');
    return `<p class="tags">${items}</p>`;
}
function formatDate(date) {
    if (!date)
        return '';
    return `<p class="date"><time datetime="${escapeHtml(date)}">${escapeHtml(date)}</time></p>`;
}
function renderPage(page) {
    const meta = formatDate(page.date) + formatTags(page.tags);
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(page.title)}</title>
</head>
<body>
  <nav><a href="index.html">&larr; Home</a></nav>
  <article>
    <h1>${escapeHtml(page.title)}</h1>
    ${meta}
    ${page.contentHtml}
  </article>
</body>
</html>
`;
}
function renderIndex(pages) {
    const sorted = [...pages].sort((a, b) => {
        const da = a.date ?? '';
        const db = b.date ?? '';
        return db.localeCompare(da);
    });
    const items = sorted
        .map((p) => {
        const date = p.date ? `<time datetime="${escapeHtml(p.date)}">${escapeHtml(p.date)}</time> ` : '';
        return `    <li><a href="${escapeHtml(p.slug)}.html">${escapeHtml(p.title)}</a> ${date}</li>`;
    })
        .join('\n');
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Home</title>
</head>
<body>
  <header><h1>Home</h1></header>
  <main>
    <ul class="pages">
${items}
    </ul>
  </main>
</body>
</html>
`;
}
