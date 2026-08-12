"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.slugify = slugify;
exports.findMarkdownFiles = findMarkdownFiles;
exports.readPages = readPages;
exports.parseMarkdown = parseMarkdown;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const markdown_it_1 = __importDefault(require("markdown-it"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const md = new markdown_it_1.default({ html: true, linkify: true, typographer: true });
function slugify(input) {
    const slug = input
        .toLowerCase()
        .trim()
        .replace(/[^\w\s-]/g, '')
        .replace(/\s+/g, '-')
        .replace(/-+/g, '-')
        .replace(/^-|-$/g, '');
    return slug || 'untitled';
}
function stripHtml(html) {
    return html.replace(/<[^>]+>/g, ' ');
}
function formatDate(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
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
    return files.map((file) => parseMarkdown(fs_1.default.readFileSync(file, 'utf8'), path_1.default.relative(contentDir, file)));
}
function parseMarkdown(content, filePath) {
    const { data, content: body } = (0, gray_matter_1.default)(content);
    const rawTitle = typeof data.title === 'string' ? data.title : '';
    const title = rawTitle.trim()
        ? rawTitle.trim()
        : path_1.default.basename(filePath, path_1.default.extname(filePath));
    const rawDate = data.date instanceof Date
        ? formatDate(data.date)
        : typeof data.date === 'string'
            ? data.date
            : undefined;
    const rawTags = data.tags;
    const tags = Array.isArray(rawTags)
        ? rawTags.filter((t) => typeof t === 'string')
        : [];
    const rawSlug = typeof data.slug === 'string' ? data.slug : '';
    const slug = slugify(rawSlug.trim() ? rawSlug : title);
    const rawTemplate = typeof data.template === 'string' ? data.template.trim() : '';
    const rawLayout = typeof data.layout === 'string' ? data.layout.trim() : '';
    const html = md.render(body);
    const excerpt = stripHtml(html).trim().replace(/\s+/g, ' ').slice(0, 200);
    return {
        title,
        slug,
        date: rawDate,
        tags,
        body,
        html,
        excerpt,
        filePath,
        template: rawTemplate || undefined,
        layout: rawLayout || undefined,
    };
}
