"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseMarkdownFiles = parseMarkdownFiles;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
const DEFAULT_FRONTMATTER = {
    title: '',
    date: '',
    tags: [],
};
function parseMarkdownFiles(contentDir) {
    const resolved = path_1.default.resolve(contentDir);
    const dirEntries = fs_1.default.readdirSync(resolved, { withFileTypes: true });
    const pages = [];
    for (const entry of dirEntries) {
        if (!entry.isFile() || !entry.name.endsWith('.md'))
            continue;
        const filePath = path_1.default.join(resolved, entry.name);
        const raw = fs_1.default.readFileSync(filePath, 'utf-8');
        const { data, content } = (0, gray_matter_1.default)(raw);
        const dateValue = data.date instanceof Date
            ? data.date.toISOString().split('T')[0]
            : typeof data.date === 'string'
                ? data.date
                : DEFAULT_FRONTMATTER.date;
        const frontmatter = {
            title: typeof data.title === 'string' ? data.title : DEFAULT_FRONTMATTER.title,
            date: dateValue,
            tags: Array.isArray(data.tags) ? data.tags : DEFAULT_FRONTMATTER.tags,
        };
        const html = marked_1.marked.parse(content);
        const slug = entry.name.replace(/\.md$/, '');
        pages.push({ slug, frontmatter, content, html });
    }
    pages.sort((a, b) => a.frontmatter.title.localeCompare(b.frontmatter.title));
    return pages;
}
//# sourceMappingURL=parser.js.map