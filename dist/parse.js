"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.slugify = slugify;
exports.parseMarkdown = parseMarkdown;
exports.readMarkdownFile = readMarkdownFile;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
function slugify(filename) {
    const base = path_1.default.basename(filename, path_1.default.extname(filename));
    return base
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
}
function parseMarkdown(content, source) {
    const { data, content: body } = (0, gray_matter_1.default)(content);
    const slug = slugify(source);
    const title = typeof data.title === 'string' && data.title.trim()
        ? data.title
        : slug;
    let date;
    if (typeof data.date === 'string' && data.date.trim()) {
        date = data.date;
    }
    else if (data.date instanceof Date && !Number.isNaN(data.date.getTime())) {
        date = data.date.toISOString().slice(0, 10);
    }
    let tags = [];
    if (Array.isArray(data.tags)) {
        tags = data.tags.map((t) => String(t).trim()).filter(Boolean);
    }
    else if (typeof data.tags === 'string') {
        tags = data.tags.split(',').map((t) => t.trim()).filter(Boolean);
    }
    const contentHtml = marked_1.marked.parse(body, { async: false });
    return { slug, title, date, tags, contentHtml, source };
}
function readMarkdownFile(filePath) {
    const content = fs_1.default.readFileSync(filePath, 'utf8');
    return parseMarkdown(content, path_1.default.basename(filePath));
}
