"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.renderPage = renderPage;
exports.renderIndex = renderIndex;
const templates_1 = require("./templates");
function escapeHtml(value) {
    return value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
function buildMeta(page) {
    const metaParts = [];
    if (page.date) {
        metaParts.push(escapeHtml(page.date));
    }
    if (page.tags.length > 0) {
        metaParts.push(`<span class="tags">${page.tags
            .map((t) => `<span>${escapeHtml(t)}</span>`)
            .join('')}</span>`);
    }
    return metaParts.join(' · ');
}
function pageContext(page) {
    return {
        ...(page.data ?? {}),
        title: page.title,
        date: page.date,
        tags: page.tags,
        slug: page.slug,
        contentHtml: page.contentHtml,
        content: page.contentHtml,
        meta: buildMeta(page),
    };
}
function renderPage(page, engine) {
    const e = engine ?? new templates_1.TemplateEngine('./templates');
    const context = pageContext(page);
    const body = e.render(page.template ?? 'default', context);
    return e.renderLayout(page.layout ?? 'default', { ...context, body });
}
function renderIndex(pages, engine) {
    const e = engine ?? new templates_1.TemplateEngine('./templates');
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
    return e.renderLayout('default', { title: 'All pages', body });
}
//# sourceMappingURL=render.js.map