"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.buildSite = buildSite;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const markdown_1 = require("./markdown");
const templates_1 = require("./templates");
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
function listMarkdownFiles(dir) {
    const files = [];
    if (!fs_1.default.existsSync(dir)) {
        return files;
    }
    for (const entry of fs_1.default.readdirSync(dir)) {
        const fullPath = path_1.default.join(dir, entry);
        const stat = fs_1.default.statSync(fullPath);
        if (stat.isDirectory()) {
            files.push(...listMarkdownFiles(fullPath));
        }
        else if (stat.isFile() && /\.md$/i.test(entry)) {
            files.push(fullPath);
        }
    }
    return files;
}
function slugForFile(filePath, contentDir) {
    const relative = path_1.default.relative(contentDir, filePath);
    const withoutExtension = relative.replace(/\.md$/i, '');
    return withoutExtension.split(path_1.default.sep).join('/');
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
function postToContext(post) {
    return {
        title: post.title,
        date: post.date,
        tags: post.tags,
        slug: post.slug,
        content: post.content,
        body: post.html,
    };
}
function buildSite(options) {
    const { contentDir, outputDir } = options;
    const templatesDir = options.templatesDir ?? path_1.default.join(process.cwd(), 'templates');
    const engine = new templates_1.TemplateEngine(templatesDir);
    const markdownFiles = listMarkdownFiles(contentDir);
    const posts = markdownFiles.map((filePath) => {
        const source = fs_1.default.readFileSync(filePath, 'utf-8');
        const { meta, content, html } = (0, markdown_1.parseMarkdown)(source);
        return {
            slug: slugForFile(filePath, contentDir),
            title: meta.title || slugForFile(filePath, contentDir),
            date: meta.date,
            tags: meta.tags,
            template: meta.template,
            content,
            html,
        };
    });
    posts.sort((a, b) => {
        const dateA = a.date ? Date.parse(a.date) : NaN;
        const dateB = b.date ? Date.parse(b.date) : NaN;
        if (!Number.isNaN(dateA) && !Number.isNaN(dateB) && dateA !== dateB) {
            return dateB - dateA;
        }
        if (Number.isNaN(dateA) && !Number.isNaN(dateB)) {
            return 1;
        }
        if (!Number.isNaN(dateA) && Number.isNaN(dateB)) {
            return -1;
        }
        return a.title.localeCompare(b.title);
    });
    fs_1.default.mkdirSync(outputDir, { recursive: true });
    const filesWritten = [];
    const indexPath = path_1.default.join(outputDir, 'index.html');
    fs_1.default.writeFileSync(indexPath, renderIndex(posts));
    filesWritten.push(indexPath);
    for (const post of posts) {
        const pagePath = path_1.default.join(outputDir, `${post.slug}.html`);
        fs_1.default.mkdirSync(path_1.default.dirname(pagePath), { recursive: true });
        const rendered = engine.render(post.template, postToContext(post));
        fs_1.default.writeFileSync(pagePath, rendered ?? renderPage(post));
        filesWritten.push(pagePath);
    }
    return { posts, filesWritten, outputDir };
}
