"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseMarkdownFile = parseMarkdownFile;
exports.readContentDirectory = readContentDirectory;
exports.generateSite = generateSite;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
const templates_1 = require("./templates");
function parseMarkdownFile(filePath) {
    const raw = fs_1.default.readFileSync(filePath, 'utf-8');
    const { data, content } = (0, gray_matter_1.default)(raw);
    const slug = path_1.default.basename(filePath, '.md');
    const parsed = marked_1.marked.parse(content);
    const html = typeof parsed === 'object' && parsed !== null && 'html' in parsed
        ? parsed.html
        : parsed;
    const date = data.date instanceof Date
        ? data.date.toISOString().split('T')[0]
        : data.date || '';
    return {
        title: data.title || slug,
        date,
        tags: data.tags || [],
        content: html,
        slug,
        layout: data.layout || undefined,
        template: data.template || undefined,
    };
}
function readContentDirectory(contentDir) {
    if (!fs_1.default.existsSync(contentDir)) {
        return [];
    }
    const entries = fs_1.default.readdirSync(contentDir);
    const pages = [];
    for (const entry of entries) {
        if (entry.endsWith('.md')) {
            const page = parseMarkdownFile(path_1.default.join(contentDir, entry));
            if (page) {
                pages.push(page);
            }
        }
    }
    return pages;
}
function renderPage(page) {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${page.title}</title>
${page.tags.length ? `  <meta name="keywords" content="${page.tags.join(', ')}">` : ''}
</head>
<body>
  <header>
    <nav><a href="index.html">Home</a></nav>
  </header>
  <main>
    <article>
      <h1>${page.title}</h1>
${page.date ? `      <time>${page.date}</time>` : ''}
      <div>${page.content}</div>
    </article>
  </main>
</body>
</html>`;
}
function renderIndex(pages) {
    const listItems = pages
        .map((page) => {
        const dateStr = page.date ? ` <time>${page.date}</time>` : '';
        const tagsStr = page.tags.length ? ` [${page.tags.join(', ')}]` : '';
        return `      <li><a href="${page.slug}.html">${page.title}</a>${dateStr}${tagsStr}</li>`;
    })
        .join('\n');
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>All Pages</title>
</head>
<body>
  <header>
    <h1>All Pages</h1>
  </header>
  <main>
    <ul>
${listItems}
    </ul>
  </main>
</body>
</html>`;
}
function generateSite(contentDir, outputDir, templatesDir) {
    const pages = readContentDirectory(contentDir);
    if (pages.length === 0) {
        console.log(`No markdown files found in ${contentDir}`);
        return 0;
    }
    fs_1.default.mkdirSync(outputDir, { recursive: true });
    const engine = templatesDir ? new templates_1.TemplateEngine(templatesDir) : null;
    const useTemplates = engine && engine.initialized;
    for (const page of pages) {
        const html = useTemplates
            ? (engine.render(page) || renderPage(page))
            : renderPage(page);
        fs_1.default.writeFileSync(path_1.default.join(outputDir, `${page.slug}.html`), html);
    }
    const indexHtml = useTemplates
        ? (engine.renderIndex(pages) || renderIndex(pages))
        : renderIndex(pages);
    fs_1.default.writeFileSync(path_1.default.join(outputDir, 'index.html'), indexHtml);
    console.log(`Generated ${pages.length + 1} files in ${outputDir}`);
    return pages.length + 1;
}
//# sourceMappingURL=generator.js.map