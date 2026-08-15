"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.generatePageHtml = generatePageHtml;
exports.generateIndexHtml = generateIndexHtml;
const path_1 = __importDefault(require("path"));
const files_1 = require("./files");
const template_1 = require("./template");
async function generatePageHtml(page, outputDir, templateDir, pluginManager) {
    let html;
    if (pluginManager) {
        const context = { contentDir: '', outputDir, templateDir };
        const processedPage = await pluginManager.runOnFile(page, context);
        html = processedPage.html;
    }
    else if (templateDir) {
        html = await createPageHtmlWithTemplate(page, templateDir);
    }
    else {
        html = createPageHtml(page);
    }
    const filePath = path_1.default.join(outputDir, `${page.slug}.html`);
    await (0, files_1.writeFile)(filePath, html);
}
async function generateIndexHtml(pages, outputDir) {
    const html = createIndexHtml(pages);
    const filePath = path_1.default.join(outputDir, 'index.html');
    await (0, files_1.writeFile)(filePath, html);
}
async function createPageHtmlWithTemplate(page, templateDir) {
    await (0, template_1.loadPartials)(templateDir);
    const eng = (0, template_1.getEngine)();
    let html = page.html;
    if (page.template) {
        const templateContent = await (0, template_1.loadTemplate)(page.template, templateDir);
        html = eng.render(templateContent, { ...page, body: page.html });
    }
    if (page.layout) {
        const layout = await (0, template_1.loadLayout)(page.layout, templateDir);
        html = eng.render(layout, { ...page, body: html });
    }
    return html;
}
function createPageHtml(page) {
    const tagsList = page.tags && Array.isArray(page.tags)
        ? `<div class="tags">${page.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}</div>`
        : '';
    const dateHtml = page.date ? `<p class="date">${escapeHtml(page.date)}</p>` : '';
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(page.title)}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; color: #333; }
    h1 { color: #000; margin-bottom: 10px; }
    .meta { color: #666; margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 10px; }
    .date { margin: 0; font-size: 0.9em; }
    .tags { margin-top: 10px; }
    .tag { display: inline-block; background: #f0f0f0; padding: 4px 8px; margin-right: 5px; border-radius: 3px; font-size: 0.85em; }
    .content { margin-top: 20px; }
    a { color: #0066cc; }
    code { background: #f5f5f5; padding: 2px 4px; border-radius: 3px; }
    pre { background: #f5f5f5; padding: 10px; border-radius: 3px; overflow-x: auto; }
    .back-link { margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
  </style>
</head>
<body>
  <article>
    <h1>${escapeHtml(page.title)}</h1>
    <div class="meta">
      ${dateHtml}
      ${tagsList}
    </div>
    <div class="content">
      ${page.html}
    </div>
  </article>
  <footer class="back-link">
    <a href="index.html">← Back to all pages</a>
  </footer>
</body>
</html>`;
}
function createIndexHtml(pages) {
    const pagesList = pages
        .sort((a, b) => {
        if (!a.date || !b.date)
            return 0;
        return new Date(b.date).getTime() - new Date(a.date).getTime();
    })
        .map(page => `
    <li>
      <a href="${escapeHtml(page.slug)}.html">${escapeHtml(page.title)}</a>
      ${page.date ? `<span class="date"> — ${escapeHtml(page.date)}</span>` : ''}
      ${page.tags && Array.isArray(page.tags) ? `<div class="tags">${page.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}</div>` : ''}
    </li>
  `).join('');
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>All Pages</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; color: #333; }
    h1 { color: #000; }
    ul { list-style: none; padding: 0; }
    li { padding: 10px 0; border-bottom: 1px solid #eee; }
    li:last-child { border-bottom: none; }
    a { color: #0066cc; text-decoration: none; font-weight: 500; }
    a:hover { text-decoration: underline; }
    .date { color: #666; font-size: 0.9em; margin-left: 10px; }
    .tags { margin-top: 5px; display: flex; flex-wrap: wrap; gap: 5px; }
    .tag { display: inline-block; background: #f0f0f0; padding: 4px 8px; border-radius: 3px; font-size: 0.85em; color: #666; }
  </style>
</head>
<body>
  <h1>All Pages</h1>
  <p>Total: ${pages.length} page${pages.length === 1 ? '' : 's'}</p>
  <ul>
    ${pagesList}
  </ul>
</body>
</html>`;
}
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, char => map[char]);
}
//# sourceMappingURL=generator.js.map