"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.generateSite = generateSite;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
function htmlEncode(str) {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
function wrapPage(title, body) {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${htmlEncode(title)}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; line-height: 1.6; }
    a { color: #2563eb; }
    nav { margin-bottom: 2rem; }
    .meta { color: #6b7280; font-size: 0.9rem; margin-bottom: 1.5rem; }
    .tags { display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .tag { background: #e5e7eb; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.85rem; }
  </style>
</head>
<body>
  <nav><a href="index.html">&larr; Home</a></nav>
  ${body}
</body>
</html>`;
}
function renderPageHtml(page) {
    const { title, date, tags } = page.frontmatter;
    const metaParts = [];
    if (date)
        metaParts.push(`<time>${htmlEncode(date)}</time>`);
    const meta = metaParts.length
        ? `<div class="meta">${metaParts.join(' &middot; ')}</div>`
        : '';
    const tagsHtml = tags && tags.length > 0
        ? `<div class="tags">${tags.map((t) => `<span class="tag">${htmlEncode(t)}</span>`).join('\n')}</div>`
        : '';
    const body = `<article>
  <h1>${htmlEncode(title)}</h1>
  ${meta}
  ${tagsHtml}
  ${page.html}
</article>`;
    return wrapPage(title, body);
}
function renderIndexHtml(pages) {
    const items = pages
        .map((p) => {
        const { title, date, tags } = p.frontmatter;
        const tagsHtml = tags && tags.length > 0
            ? ` <span class="tags">${tags.map((t) => `<span class="tag">${htmlEncode(t)}</span>`).join(' ')}</span>`
            : '';
        const dateHtml = date ? ` <time>${htmlEncode(date)}</time>` : '';
        return `<li>
      <a href="${htmlEncode(p.slug)}.html">${htmlEncode(title)}</a>${dateHtml}${tagsHtml}
    </li>`;
    })
        .join('\n');
    const body = `<h1>All Posts</h1>
  <ul>
    ${items}
  </ul>`;
    return wrapPage('Index', body);
}
function generateSite(pages, outputDir) {
    fs_1.default.mkdirSync(outputDir, { recursive: true });
    for (const page of pages) {
        const html = renderPageHtml(page);
        fs_1.default.writeFileSync(path_1.default.join(outputDir, `${page.slug}.html`), html, 'utf-8');
    }
    const indexHtml = renderIndexHtml(pages);
    fs_1.default.writeFileSync(path_1.default.join(outputDir, 'index.html'), indexHtml, 'utf-8');
}
//# sourceMappingURL=generator.js.map