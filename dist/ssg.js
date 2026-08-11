"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.build = build;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
function slugify(filename) {
    const name = path_1.default.basename(filename, path_1.default.extname(filename));
    return name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
}
function readMarkdownFiles(contentDir) {
    if (!fs_1.default.existsSync(contentDir)) {
        return [];
    }
    return fs_1.default.readdirSync(contentDir)
        .filter(f => f.endsWith('.md'))
        .map(f => path_1.default.join(contentDir, f));
}
function parsePage(filePath) {
    const raw = fs_1.default.readFileSync(filePath, 'utf-8');
    const { data, content } = (0, gray_matter_1.default)(raw);
    const html = marked_1.marked.parse(content);
    const slug = slugify(path_1.default.basename(filePath));
    return {
        frontmatter: {
            title: data.title || slug,
            date: data.date,
            tags: data.tags,
        },
        html,
        slug,
    };
}
function buildPageHTML(page) {
    const { title, date, tags } = page.frontmatter;
    const tagsHtml = tags && tags.length > 0
        ? `<div class="tags">Tags: ${tags.join(', ')}</div>`
        : '';
    const dateHtml = date
        ? `<div class="date">${new Date(date).toLocaleDateString()}</div>`
        : '';
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
</head>
<body>
  <main>
    <article>
      <h1>${title}</h1>
      ${dateHtml}
      ${tagsHtml}
      ${page.html}
    </article>
  </main>
  <footer>
    <a href="index.html">Back to index</a>
  </footer>
</body>
</html>`;
}
function buildIndexHTML(pages) {
    const listItems = pages
        .map(page => {
        const { title, date, tags } = page.frontmatter;
        const dateStr = date ? ` — ${new Date(date).toLocaleDateString()}` : '';
        const tagsStr = tags && tags.length > 0 ? ` [${tags.join(', ')}]` : '';
        return `<li><a href="${page.slug}.html">${title}</a>${dateStr}${tagsStr}</li>`;
    })
        .join('\n      ');
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>My Static Site</title>
</head>
<body>
  <main>
    <h1>Pages</h1>
    <ul>
      ${listItems}
    </ul>
  </main>
</body>
</html>`;
}
function build(options) {
    const { contentDir, outputDir } = options;
    if (!fs_1.default.existsSync(outputDir)) {
        fs_1.default.mkdirSync(outputDir, { recursive: true });
    }
    const files = readMarkdownFiles(contentDir);
    const pages = [];
    for (const file of files) {
        const page = parsePage(file);
        pages.push(page);
        const pageHTML = buildPageHTML(page);
        const outPath = path_1.default.join(outputDir, `${page.slug}.html`);
        fs_1.default.writeFileSync(outPath, pageHTML, 'utf-8');
    }
    const indexHTML = buildIndexHTML(pages);
    fs_1.default.writeFileSync(path_1.default.join(outputDir, 'index.html'), indexHTML, 'utf-8');
}
//# sourceMappingURL=ssg.js.map