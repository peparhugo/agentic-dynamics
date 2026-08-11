"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseMarkdownFile = parseMarkdownFile;
exports.parseMarkdownDirectory = parseMarkdownDirectory;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
function parseMarkdownFile(filePath) {
    const raw = fs_1.default.readFileSync(filePath, 'utf-8');
    const parsed = (0, gray_matter_1.default)(raw);
    const data = parsed.data;
    const frontmatter = {
        title: data.title,
        date: data.date instanceof Date ? data.date.toISOString().slice(0, 10) : data.date != null ? String(data.date) : undefined,
        tags: data.tags,
        template: data.template,
        layout: data.layout,
    };
    if (!frontmatter.title) {
        throw new Error(`Missing required frontmatter field "title" in ${filePath}`);
    }
    const html = marked_1.marked.parse(parsed.content);
    const slug = path_1.default.basename(filePath, path_1.default.extname(filePath));
    return {
        frontmatter,
        content: parsed.content,
        html,
        slug,
        sourcePath: filePath,
    };
}
function parseMarkdownDirectory(contentDir) {
    if (!fs_1.default.existsSync(contentDir)) {
        throw new Error(`Content directory not found: ${contentDir}`);
    }
    const entries = fs_1.default.readdirSync(contentDir);
    const pages = [];
    for (const entry of entries) {
        const fullPath = path_1.default.join(contentDir, entry);
        const stat = fs_1.default.statSync(fullPath);
        if (stat.isFile() && (entry.endsWith('.md') || entry.endsWith('.markdown'))) {
            pages.push(parseMarkdownFile(fullPath));
        }
    }
    return pages.sort((a, b) => {
        const dateA = a.frontmatter.date || '';
        const dateB = b.frontmatter.date || '';
        return dateB.localeCompare(dateA);
    });
}
