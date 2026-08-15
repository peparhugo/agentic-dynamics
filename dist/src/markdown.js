"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseMarkdown = parseMarkdown;
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
const frontmatter_1 = require("./frontmatter");
/**
 * Parse a Markdown source string into structured page data.
 *
 * gray-matter only parses JSON frontmatter, so we parse the `---`-delimited
 * YAML block ourselves and merge it into gray-matter's output before handing
 * the data to the renderer.
 */
function parseMarkdown(source, sourcePath, slug) {
    const yamlData = (0, frontmatter_1.parseFrontmatter)(source);
    const gm = (0, gray_matter_1.default)(source);
    const merged = { ...gm.data, ...yamlData };
    const title = readString(merged.title) || slug;
    const date = readString(merged.date);
    const tags = readTags(merged.tags);
    const html = marked_1.marked.parse(gm.content, { async: false });
    return {
        slug,
        title,
        date,
        tags,
        content: gm.content,
        html,
        sourcePath,
        data: merged,
        template: readString(merged.template),
        layout: readString(merged.layout),
    };
}
function readString(value) {
    if (typeof value === 'string' && value.trim() !== '') {
        return value;
    }
    if (value instanceof Date) {
        return value.toISOString();
    }
    return undefined;
}
function readTags(value) {
    if (Array.isArray(value)) {
        return value
            .map((tag) => String(tag).trim())
            .filter((tag) => tag.length > 0);
    }
    if (typeof value === 'string' && value.trim() !== '') {
        return value
            .split(',')
            .map((tag) => tag.trim())
            .filter((tag) => tag.length > 0);
    }
    return [];
}
