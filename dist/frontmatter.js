"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseFrontmatter = parseFrontmatter;
exports.normalizeTags = normalizeTags;
const gray_matter_1 = __importDefault(require("gray-matter"));
const FRONTMATTER_RE = /^\uFEFF?---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*(\r?\n|$)/;
function normalizeDate(value) {
    if (value == null) {
        return undefined;
    }
    if (value instanceof Date) {
        return value.toISOString().slice(0, 10);
    }
    return String(value);
}
/**
 * Strips the leading YAML frontmatter block (delimited by `---`) using a
 * regex, then parses the YAML with gray-matter. Stripping manually before
 * handing the body to `marked` is required: otherwise `marked` renders the
 * `---` delimiter block as literal HTML text.
 */
function parseFrontmatter(raw) {
    const match = FRONTMATTER_RE.exec(raw);
    if (!match) {
        return { data: {}, body: raw };
    }
    const yaml = match[1];
    const body = raw.slice(match[0].length);
    const parsed = (0, gray_matter_1.default)(`---\n${yaml}\n---\n`);
    const data = parsed.data ?? {};
    return {
        data: {
            title: data.title,
            date: normalizeDate(data.date),
            tags: data.tags,
        },
        body,
    };
}
function normalizeTags(tags) {
    if (tags == null) {
        return [];
    }
    if (Array.isArray(tags)) {
        return tags.map((t) => String(t).trim()).filter(Boolean);
    }
    if (typeof tags === 'string') {
        return tags
            .split(',')
            .map((t) => t.trim())
            .filter(Boolean);
    }
    return [];
}
//# sourceMappingURL=frontmatter.js.map