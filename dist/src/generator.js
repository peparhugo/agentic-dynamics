"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.generatePageHtml = generatePageHtml;
exports.generateIndexHtml = generateIndexHtml;
function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
function generatePageHtml(page, engine) {
    if (engine) {
        return engine.renderPage(page);
    }
    const { title, date, tags } = page.frontmatter;
    const dateStr = date || '';
    const tagsStr = tags ? tags.map((t) => escapeHtml(t)).join(', ') : '';
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(title)}</title>
</head>
<body>
  <header>
    <nav><a href="index.html">Home</a></nav>
  </header>
  <main>
    <article>
      <h1>${escapeHtml(title)}</h1>
      ${dateStr ? `<time datetime="${escapeHtml(dateStr)}">${escapeHtml(dateStr)}</time>` : ''}
      ${tagsStr ? `<p>Tags: ${tagsStr}</p>` : ''}
      <div>${page.html}</div>
    </article>
  </main>
</body>
</html>`;
}
function generateIndexHtml(pages, engine) {
    if (engine) {
        return engine.renderIndex(pages);
    }
    const items = pages
        .map((page) => {
        const { title, date, tags } = page.frontmatter;
        const dateStr = date || '';
        const tagsStr = tags ? tags.map((t) => escapeHtml(t)).join(', ') : '';
        return `      <li>
        <a href="${escapeHtml(page.slug)}.html">${escapeHtml(title)}</a>
        ${dateStr ? `<span>${escapeHtml(dateStr)}</span>` : ''}
        ${tagsStr ? `<span>Tags: ${tagsStr}</span>` : ''}
      </li>`;
    })
        .join('\n');
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Index</title>
</head>
<body>
  <header>
    <h1>All Pages</h1>
  </header>
  <main>
    <ul>
${items}
    </ul>
  </main>
</body>
</html>`;
}
