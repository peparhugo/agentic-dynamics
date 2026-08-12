"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.DEFAULT_OUTPUT_DIR = exports.DEFAULT_CONTENT_DIR = void 0;
exports.findMarkdownFiles = findMarkdownFiles;
exports.readPages = readPages;
exports.sortPages = sortPages;
exports.renderPage = renderPage;
exports.renderIndex = renderIndex;
exports.buildSite = buildSite;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const markdown_1 = require("./markdown");
exports.DEFAULT_CONTENT_DIR = 'content';
exports.DEFAULT_OUTPUT_DIR = 'dist';
function escapeHtml(input) {
    return input
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
function findMarkdownFiles(contentDir) {
    const results = [];
    const walk = (dir) => {
        const entries = fs_1.default.readdirSync(dir, { withFileTypes: true });
        for (const entry of entries) {
            const full = path_1.default.join(dir, entry.name);
            if (entry.isDirectory()) {
                walk(full);
            }
            else if (entry.isFile() && /\.mdx?$/i.test(entry.name)) {
                results.push(full);
            }
        }
    };
    walk(contentDir);
    results.sort();
    return results;
}
function readPages(contentDir) {
    const files = findMarkdownFiles(contentDir);
    return files.map((file) => (0, markdown_1.parseMarkdown)(fs_1.default.readFileSync(file, 'utf8'), path_1.default.relative(contentDir, file)));
}
function sortPages(pages) {
    return [...pages].sort((a, b) => {
        const da = a.date ? new Date(a.date).getTime() : 0;
        const db = b.date ? new Date(b.date).getTime() : 0;
        if (da !== db)
            return db - da;
        return a.title.localeCompare(b.title);
    });
}
function renderTags(tags) {
    return tags
        .map((tag) => `<a class="tag" href="?tag=${encodeURIComponent(tag)}">${escapeHtml(tag)}</a>`)
        .join('');
}
function renderPage(page) {
    const dateHtml = page.date
        ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>`
        : '';
    return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(page.title)}</title>
</head>
<body>
<nav><a href="./index.html">Home</a></nav>
<main>
<article>
<h1>${escapeHtml(page.title)}</h1>
${dateHtml}
<div class="tags">${renderTags(page.tags)}</div>
<div class="content">
${page.html}
</div>
</article>
</main>
</body>
</html>
`;
}
function renderIndex(pages) {
    const items = pages
        .map((page) => {
        const dateHtml = page.date
            ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>`
            : '';
        const tagsHtml = page.tags
            .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
            .join(' ');
        return `    <li class="page">
      <h2><a href="${escapeHtml(page.slug)}.html">${escapeHtml(page.title)}</a></h2>
      <p class="meta">${dateHtml} ${tagsHtml}</p>
      <p class="excerpt">${escapeHtml(page.excerpt)}</p>
    </li>`;
    })
        .join('\n');
    return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Home</title>
</head>
<body>
<main>
<h1>Pages</h1>
<ul class="pages">
${items}
</ul>
</main>
</body>
</html>
`;
}
function buildSite(contentDir, outputDir) {
    if (!fs_1.default.existsSync(contentDir)) {
        throw new Error(`content directory not found: ${contentDir}`);
    }
    const pages = sortPages(readPages(contentDir));
    fs_1.default.mkdirSync(outputDir, { recursive: true });
    const files = [];
    for (const page of pages) {
        const name = `${page.slug}.html`;
        fs_1.default.writeFileSync(path_1.default.join(outputDir, name), renderPage(page), 'utf8');
        files.push(name);
    }
    fs_1.default.writeFileSync(path_1.default.join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
    files.push('index.html');
    return { pages: pages.length, outputDir, files };
}
