"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseFiles = parseFiles;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
function parseFiles({ contentDir }) {
    if (!fs_1.default.existsSync(contentDir)) {
        throw new Error(`Content directory not found: ${contentDir}`);
    }
    const files = fs_1.default.readdirSync(contentDir).filter((f) => f.endsWith('.md'));
    const pages = files.map((file) => {
        const filePath = path_1.default.join(contentDir, file);
        const raw = fs_1.default.readFileSync(filePath, 'utf-8');
        const { data, content } = (0, gray_matter_1.default)(raw);
        const frontmatter = {
            title: String(data.title || file.replace(/\.md$/, '')),
            date: formatDate(data.date),
            tags: Array.isArray(data.tags) ? data.tags.map(String) : [],
            template: data.template ? String(data.template) : undefined,
            layout: data.layout ? String(data.layout) : undefined,
        };
        const html = marked_1.marked.parse(content.trim());
        const slug = file.replace(/\.md$/, '');
        return { slug, frontmatter, content, html };
    });
    return { pages };
}
function formatDate(date) {
    if (date instanceof Date) {
        return date.toISOString().split('T')[0];
    }
    if (typeof date === 'string') {
        const match = date.match(/^\d{4}-\d{2}-\d{2}/);
        if (match) {
            return match[0];
        }
    }
    return '';
}
