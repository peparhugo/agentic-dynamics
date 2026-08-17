"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.splitFrontmatter = splitFrontmatter;
exports.normalizeDate = normalizeDate;
exports.parseMarkdown = parseMarkdown;
exports.escapeHtml = escapeHtml;
exports.normalizeTags = normalizeTags;
exports.defaultTitle = defaultTitle;
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
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
//# sourceMappingURL=markdown.js.map