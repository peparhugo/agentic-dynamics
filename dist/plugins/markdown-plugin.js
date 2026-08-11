"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.MarkdownPlugin = void 0;
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
function normalizeDate(d) {
    if (d instanceof Date)
        return d.toISOString().slice(0, 10);
    if (typeof d === 'string')
        return d;
    return undefined;
}
function normalizeTags(t) {
    if (Array.isArray(t))
        return t.map((v) => String(v));
    return undefined;
}
function normalizeVal(v) {
    if (typeof v === 'string')
        return v;
    return undefined;
}
class MarkdownPlugin {
    constructor() {
        this.name = 'markdown';
    }
    onFile(page) {
        const raw = (0, gray_matter_1.default)(page.content);
        page.title = String(raw.data.title || page.slug);
        page.date = normalizeDate(raw.data.date);
        page.tags = normalizeTags(raw.data.tags);
        page.template = normalizeVal(raw.data.template);
        page.layout = normalizeVal(raw.data.layout);
        page.content = raw.content;
        page.html = marked_1.marked.parse(raw.content);
    }
}
exports.MarkdownPlugin = MarkdownPlugin;
//# sourceMappingURL=markdown-plugin.js.map