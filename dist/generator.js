"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.buildSite = buildSite;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const markdown_it_1 = __importDefault(require("markdown-it"));
const handlebars_1 = __importDefault(require("handlebars"));
const md = new markdown_it_1.default();
function parseMarkdownFile(filePath) {
    const raw = fs_1.default.readFileSync(filePath, 'utf-8');
    const parsed = (0, gray_matter_1.default)(raw);
    const title = String(parsed.data.title || 'Untitled');
    const rawDate = parsed.data.date;
    const date = rawDate instanceof Date ? rawDate.toISOString().slice(0, 10) : String(rawDate || '');
    const tags = Array.isArray(parsed.data.tags)
        ? parsed.data.tags.map((t) => String(t))
        : [];
    const template = parsed.data.template ? String(parsed.data.template) : undefined;
    const content = parsed.content;
    const html = md.render(content);
    const slug = path_1.default.basename(filePath, path_1.default.extname(filePath));
    return { title, date, tags, content, html, slug, template };
}
function generatePageHtml(page) {
    const tagsHtml = page.tags.map((t) => `<span class="tag">${t}</span>`).join(' ');
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(page.title)}</title>
  <style>
    body { font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; }
    .tag { background: #e0e0e0; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.85rem; margin-right: 0.5rem; }
    .date { color: #666; font-size: 0.9rem; }
    nav a { margin-right: 1rem; }
  </style>
</head>
<body>
  <nav><a href="index.html">Home</a></nav>
  <h1>${escapeHtml(page.title)}</h1>
  <p class="date">${escapeHtml(page.date)}</p>
  <div class="tags">${tagsHtml}</div>
  <article>${page.html}</article>
</body>
</html>`;
}
function generateIndexHtml(pages) {
    const items = pages
        .map((p) => `
    <li>
      <a href="${escapeHtml(p.slug)}.html">${escapeHtml(p.title)}</a>
      <span class="date">${escapeHtml(p.date)}</span>
    </li>`)
        .join('');
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Site Index</title>
  <style>
    body { font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; }
    .date { color: #666; font-size: 0.9rem; margin-left: 1rem; }
    li { margin-bottom: 0.5rem; }
  </style>
</head>
<body>
  <h1>All Pages</h1>
  <ul>${items}
  </ul>
</body>
</html>`;
}
function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
function pageBodyHtml(page) {
    const tagsHtml = page.tags.map((t) => `<span class="tag">${t}</span>`).join(' ');
    return `<h1>${escapeHtml(page.title)}</h1>
<p class="date">${escapeHtml(page.date)}</p>
<div class="tags">${tagsHtml}</div>
<article>${page.html}</article>`;
}
function indexBodyHtml(pages) {
    const items = pages
        .map((p) => `
    <li>
      <a href="${escapeHtml(p.slug)}.html">${escapeHtml(p.title)}</a>
      <span class="date">${escapeHtml(p.date)}</span>
    </li>`)
        .join('');
    return `<h1>All Pages</h1>
  <ul>${items}
  </ul>`;
}
class TemplateEngine {
    constructor(templatesDir) {
        this.layouts = new Map();
        this.hasLayouts = false;
        this.loadTemplates(templatesDir);
    }
    loadTemplates(templatesDir) {
        const layoutsDir = path_1.default.join(templatesDir, 'layouts');
        const partialsDir = path_1.default.join(templatesDir, 'partials');
        if (fs_1.default.existsSync(partialsDir)) {
            const partialFiles = fs_1.default.readdirSync(partialsDir).filter((f) => f.endsWith('.hbs'));
            for (const file of partialFiles) {
                const name = path_1.default.basename(file, '.hbs');
                const content = fs_1.default.readFileSync(path_1.default.join(partialsDir, file), 'utf-8');
                handlebars_1.default.registerPartial(name, content);
            }
        }
        if (fs_1.default.existsSync(layoutsDir)) {
            const layoutFiles = fs_1.default.readdirSync(layoutsDir).filter((f) => f.endsWith('.hbs'));
            for (const file of layoutFiles) {
                const name = path_1.default.basename(file, '.hbs');
                const content = fs_1.default.readFileSync(path_1.default.join(layoutsDir, file), 'utf-8');
                this.layouts.set(name, handlebars_1.default.compile(content));
            }
        }
        this.hasLayouts = this.layouts.size > 0;
    }
    isActive() {
        return this.hasLayouts;
    }
    getLayout(name) {
        if (name && this.layouts.has(name)) {
            return this.layouts.get(name);
        }
        const defaultLayout = this.layouts.get('default');
        if (defaultLayout) {
            return defaultLayout;
        }
        throw new Error(`Template layout not found: ${name || 'default'}`);
    }
    renderPage(page) {
        const layout = this.getLayout(page.template);
        const body = pageBodyHtml(page);
        const tagsHtml = page.tags.map((t) => `<span class="tag">${t}</span>`).join(' ');
        const now = new Date();
        return layout({
            title: page.title,
            date: page.date,
            tags: page.tags,
            tagsHtml,
            slug: page.slug,
            body,
            year: now.getFullYear(),
        });
    }
    renderIndex(pages) {
        const layout = this.getLayout();
        const body = indexBodyHtml(pages);
        const now = new Date();
        return layout({
            title: 'Site Index',
            body,
            pages,
            year: now.getFullYear(),
        });
    }
}
function buildSite(contentDir, outputDir, templatesDir) {
    if (!fs_1.default.existsSync(contentDir)) {
        throw new Error(`Content directory does not exist: ${contentDir}`);
    }
    if (!fs_1.default.existsSync(outputDir)) {
        fs_1.default.mkdirSync(outputDir, { recursive: true });
    }
    const files = fs_1.default.readdirSync(contentDir).filter((f) => f.endsWith('.md'));
    const pages = [];
    for (const file of files) {
        const filePath = path_1.default.join(contentDir, file);
        const page = parseMarkdownFile(filePath);
        if (page) {
            pages.push(page);
        }
    }
    pages.sort((a, b) => b.date.localeCompare(a.date));
    let engine = null;
    if (templatesDir && fs_1.default.existsSync(templatesDir)) {
        const candidate = new TemplateEngine(templatesDir);
        if (candidate.isActive()) {
            engine = candidate;
        }
    }
    for (const page of pages) {
        const html = engine ? engine.renderPage(page) : generatePageHtml(page);
        const outPath = path_1.default.join(outputDir, `${page.slug}.html`);
        fs_1.default.writeFileSync(outPath, html, 'utf-8');
    }
    const indexHtml = engine ? engine.renderIndex(pages) : generateIndexHtml(pages);
    fs_1.default.writeFileSync(path_1.default.join(outputDir, 'index.html'), indexHtml, 'utf-8');
}
//# sourceMappingURL=generator.js.map