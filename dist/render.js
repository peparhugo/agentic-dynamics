"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.escapeHtml = escapeHtml;
exports.renderIndex = renderIndex;
exports.renderPage = renderPage;
exports.pageToContext = pageToContext;
function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (ch) => {
        switch (ch) {
            case '&':
                return '&amp;';
            case '<':
                return '&lt;';
            case '>':
                return '&gt;';
            case '"':
                return '&quot;';
            case "'":
                return '&#39;';
            default:
                return ch;
        }
    });
}
function renderIndex(posts) {
    const items = posts
        .map((post) => {
        const href = `${post.slug}.html`;
        const title = escapeHtml(post.title || post.slug);
        const date = post.date
            ? `<time datetime="${escapeHtml(post.date)}">${escapeHtml(post.date)}</time>`
            : '';
        const tags = post.tags.length
            ? `<span class="tags">${post.tags.map(escapeHtml).join(', ')}</span>`
            : '';
        const meta = [date, tags].filter(Boolean).join(' ');
        return `<li><a href="${href}">${title}</a>${meta ? ` — ${meta}` : ''}</li>`;
    })
        .join('\n    ');
    return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Site Index</title>
</head>
<body>
  <header><h1>Site Index</h1></header>
  <main>
    <ul>
    ${items || '<li>(no pages)</li>'}
    </ul>
  </main>
</body>
</html>
`;
}
function renderPage(post) {
    const title = escapeHtml(post.title || post.slug);
    const date = post.date
        ? `<time datetime="${escapeHtml(post.date)}">${escapeHtml(post.date)}</time>`
        : '';
    const tags = post.tags.length
        ? `<p class="tags">Tags: ${post.tags.map(escapeHtml).join(', ')}</p>`
        : '';
    return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title}</title>
</head>
<body>
  <header>
    <a href="index.html">← Index</a>
    <h1>${title}</h1>
    ${date ? `<p>${date}</p>` : ''}
    ${tags}
  </header>
  <main>
${post.html}
  </main>
</body>
</html>
`;
}
function pageToContext(post) {
    return {
        title: post.title,
        date: post.date,
        tags: post.tags,
        slug: post.slug,
        content: post.content,
        body: post.html,
    };
}
