"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.splitFrontmatter = splitFrontmatter;
exports.parseMarkdown = parseMarkdown;
exports.escapeHtml = escapeHtml;
exports.buildSite = buildSite;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
const templates_1 = require("./templates");
const DEFAULT_CONTENT_DIR = 'content';
const DEFAULT_OUTPUT_DIR = 'dist';
const DEFAULT_TEMPLATES_DIR = 'templates';
// Matches a YAML frontmatter block. The opening `---` may be preceded only by
// optional leading whitespace so that marked never sees the delimiters.
const FRONTMATTER_REGEX = /^\s*---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*\r?\n?/;
/**
 * Split raw markdown into frontmatter data and the markdown body.
 *
 * The frontmatter block is stripped manually with a regex before the body is
 * handed to `marked`, otherwise `marked` renders the `---` delimiters as a
 * literal horizontal rule. gray-matter is used only to parse the YAML data.
 */
function splitFrontmatter(raw) {
    const match = raw.match(FRONTMATTER_REGEX);
    if (!match) {
        return { data: {}, body: raw };
    }
    let data = {};
    try {
        // gray-matter requires the opening `---` to be the very first bytes of its
        // input, so rebuild a clean block (leading whitespace already stripped).
        data = (0, gray_matter_1.default)(`---\n${match[1]}\n---`).data ?? {};
    }
    catch {
        data = {};
    }
    const body = raw.slice(match[0].length);
    return { data, body };
}
function normalizeDate(value) {
    if (value == null)
        return undefined;
    if (value instanceof Date) {
        return value.toISOString().slice(0, 10);
    }
    const str = String(value).trim();
    return str.length > 0 ? str : undefined;
}
/**
 * Parse raw markdown (with optional frontmatter) into frontmatter data and
 * rendered HTML. The returned HTML is a document fragment (no <html>/<body>).
 */
function parseMarkdown(raw) {
    const { data, body } = splitFrontmatter(raw);
    const html = marked_1.marked.parse(body, { async: false });
    return {
        frontmatter: { ...data, date: normalizeDate(data.date) },
        html,
    };
}
function escapeHtml(input) {
    return input
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
function normalizeTags(tags) {
    if (Array.isArray(tags)) {
        return tags.map((t) => String(t));
    }
    if (typeof tags === 'string') {
        return tags
            .split(',')
            .map((t) => t.trim())
            .filter((t) => t.length > 0);
    }
    return [];
}
function defaultTitle(slug) {
    return slug
        .split(/[/\\-]/)
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ');
}
function listMarkdownFiles(dir) {
    if (!fs_1.default.existsSync(dir)) {
        return [];
    }
    const results = [];
    const entries = fs_1.default.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
        const full = path_1.default.join(dir, entry.name);
        if (entry.isDirectory()) {
            results.push(...listMarkdownFiles(full));
        }
        else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
            results.push(full);
        }
    }
    return results;
}
function deriveSlug(filePath, contentDir) {
    const relative = path_1.default.relative(contentDir, filePath);
    const parsed = path_1.default.parse(relative);
    return path_1.default.join(parsed.dir, parsed.name).split(path_1.default.sep).join('/');
}
function pageSummary(page) {
    return {
        slug: page.slug,
        title: page.title,
        date: page.date,
        tags: page.tags,
        url: `${page.slug}.html`,
    };
}
function buildPageContext(page, pages) {
    return {
        ...page.frontmatter,
        title: page.title,
        date: page.date,
        tags: page.tags,
        slug: page.slug,
        content: page.html,
        body: page.html,
        site: {
            pages: pages.map(pageSummary),
        },
    };
}
function renderIndex(pages) {
    const items = pages
        .map((page) => {
        const date = page.date ? ` <span class="date">${escapeHtml(page.date)}</span>` : '';
        return `<li><a href="${escapeHtml(page.slug)}.html">${escapeHtml(page.title)}</a>${date}</li>`;
    })
        .join('\n');
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Index</title>
</head>
<body>
<h1>All Pages</h1>
<ul>
${items}
</ul>
</body>
</html>
`;
}
/**
 * Build the static site: read markdown from contentDir and write HTML files
 * (one per page plus an index.html) into outputDir.
 */
function buildSite(options) {
    const contentDir = path_1.default.resolve(options.contentDir ?? DEFAULT_CONTENT_DIR);
    const outputDir = path_1.default.resolve(options.outputDir ?? DEFAULT_OUTPUT_DIR);
    const templatesDir = options.templatesDir ?? DEFAULT_TEMPLATES_DIR;
    const files = listMarkdownFiles(contentDir).sort();
    const pages = files.map((file) => {
        const raw = fs_1.default.readFileSync(file, 'utf8');
        const { frontmatter, html } = parseMarkdown(raw);
        const slug = deriveSlug(file, contentDir);
        return {
            slug,
            title: frontmatter.title ?? defaultTitle(slug),
            date: frontmatter.date != null ? String(frontmatter.date) : undefined,
            tags: normalizeTags(frontmatter.tags),
            html,
            sourcePath: file,
            frontmatter,
            template: typeof frontmatter.template === 'string' ? frontmatter.template : undefined,
            layout: frontmatter.layout,
        };
    });
    pages.sort((a, b) => {
        if (a.date && b.date) {
            return b.date.localeCompare(a.date);
        }
        if (a.date)
            return -1;
        if (b.date)
            return 1;
        return a.title.localeCompare(b.title);
    });
    fs_1.default.mkdirSync(outputDir, { recursive: true });
    const engine = new templates_1.TemplateEngine(templatesDir, {
        defaultTemplate: options.defaultTemplate ?? templates_1.DEFAULT_TEMPLATE_NAME,
        defaultLayout: options.defaultLayout ?? templates_1.DEFAULT_LAYOUT_NAME,
    });
    for (const page of pages) {
        const rendered = engine.render(page.template, page.layout, buildPageContext(page, pages));
        const outFile = path_1.default.join(outputDir, `${page.slug}.html`);
        fs_1.default.mkdirSync(path_1.default.dirname(outFile), { recursive: true });
        fs_1.default.writeFileSync(outFile, rendered);
    }
    fs_1.default.writeFileSync(path_1.default.join(outputDir, 'index.html'), renderIndex(pages));
    return { pages, outputDir };
}
//# sourceMappingURL=index.js.map