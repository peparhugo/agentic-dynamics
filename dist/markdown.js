"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.normalizeTags = normalizeTags;
exports.renderMarkdown = renderMarkdown;
exports.parseMarkdown = parseMarkdown;
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
function normalizeTags(tags) {
    if (tags == null) {
        return [];
    }
    if (Array.isArray(tags)) {
        return tags.map((tag) => String(tag).trim()).filter((tag) => tag.length > 0);
    }
    if (typeof tags === 'string') {
        return tags
            .split(',')
            .map((tag) => tag.trim())
            .filter((tag) => tag.length > 0);
    }
    const value = String(tags).trim();
    return value ? [value] : [];
}
function normalizeDate(date) {
    if (date instanceof Date) {
        return date.toISOString().slice(0, 10);
    }
    if (typeof date === 'string' && date.trim().length > 0) {
        return date.trim();
    }
    return undefined;
}
function renderMarkdown(content) {
    return marked_1.marked.parse(content);
}
/**
 * Parse a Markdown document with YAML frontmatter.
 *
 * gray-matter strips the `---` delimited frontmatter and returns the body in
 * `content`. We only ever pass that stripped body to `marked`, so the
 * frontmatter delimiter is never rendered as literal HTML.
 */
function parseMarkdown(source) {
    const { data, content } = (0, gray_matter_1.default)(source);
    const meta = {
        title: typeof data.title === 'string' ? data.title : '',
        tags: normalizeTags(data.tags),
    };
    const date = normalizeDate(data.date);
    if (date) {
        meta.date = date;
    }
    const html = renderMarkdown(content);
    return { meta, content, html };
}
