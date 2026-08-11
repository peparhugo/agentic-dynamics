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
function readPages(contentDir) {
    const absDir = path_1.default.resolve(contentDir);
    if (!fs_1.default.existsSync(absDir)) {
        throw new Error(`Content directory not found: ${absDir}`);
    }
    const entries = fs_1.default.readdirSync(absDir, { withFileTypes: true });
    const pages = [];
    for (const entry of entries) {
        if (!entry.isFile() || !entry.name.endsWith('.md')) {
            continue;
        }
        const filePath = path_1.default.join(absDir, entry.name);
        const raw = fs_1.default.readFileSync(filePath, 'utf-8');
        const parsed = (0, gray_matter_1.default)(raw);
        const slug = entry.name.replace(/\.md$/, '');
        const rawData = parsed.data;
        if (!rawData.title || typeof rawData.title !== 'string') {
            throw new Error(`Missing title in frontmatter for: ${entry.name}`);
        }
        let date;
        if (rawData.date instanceof Date) {
            date = rawData.date.toISOString().split('T')[0];
        }
        else if (typeof rawData.date === 'string') {
            date = rawData.date;
        }
        let tags;
        if (Array.isArray(rawData.tags)) {
            tags = rawData.tags.map((t) => String(t));
        }
        pages.push({
            frontmatter: {
                title: rawData.title,
                date,
                tags,
            },
            content: parsed.content,
            slug,
        });
    }
    pages.sort((a, b) => {
        if (a.frontmatter.date && b.frontmatter.date) {
            return new Date(b.frontmatter.date).getTime() - new Date(a.frontmatter.date).getTime();
        }
        if (a.frontmatter.date)
            return -1;
        if (b.frontmatter.date)
            return 1;
        return a.frontmatter.title.localeCompare(b.frontmatter.title);
    });
    return pages;
}
function renderPageTemplate(page) {
    const htmlContent = marked_1.marked.parse(page.content, { async: false });
    const dateStr = page.frontmatter.date
        ? `<p class="date">${page.frontmatter.date}</p>`
        : '';
    const tagsStr = page.frontmatter.tags && page.frontmatter.tags.length > 0
        ? `<p class="tags">Tags: ${page.frontmatter.tags.join(', ')}</p>`
        : '';
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${page.frontmatter.title}</title>
</head>
<body>
  <nav><a href="index.html">Home</a></nav>
  <article>
    <h1>${page.frontmatter.title}</h1>
    ${dateStr}
    ${tagsStr}
    <div>${htmlContent}</div>
  </article>
</body>
</html>`;
}
function renderIndexTemplate(pages) {
    const listItems = pages
        .map((page) => {
        const dateStr = page.frontmatter.date
            ? `<span class="date">${page.frontmatter.date}</span>`
            : '';
        return `    <li><a href="${page.slug}.html">${page.frontmatter.title}</a> ${dateStr}</li>`;
    })
        .join('\n');
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>My Site</title>
</head>
<body>
  <h1>All Pages</h1>
  <ul>
${listItems}
  </ul>
</body>
</html>`;
}
function build(options) {
    const { contentDir, outputDir } = options;
    const pages = readPages(contentDir);
    const absOutputDir = path_1.default.resolve(outputDir);
    fs_1.default.mkdirSync(absOutputDir, { recursive: true });
    for (const page of pages) {
        const html = renderPageTemplate(page);
        const outPath = path_1.default.join(absOutputDir, `${page.slug}.html`);
        fs_1.default.writeFileSync(outPath, html, 'utf-8');
    }
    const indexHtml = renderIndexTemplate(pages);
    fs_1.default.writeFileSync(path_1.default.join(absOutputDir, 'index.html'), indexHtml, 'utf-8');
}
//# sourceMappingURL=build.js.map