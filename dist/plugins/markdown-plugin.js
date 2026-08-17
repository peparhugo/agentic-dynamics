"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.MarkdownPlugin = void 0;
const fs_1 = __importDefault(require("fs"));
const markdown_1 = require("../markdown");
/**
 * Built-in plugin that parses raw markdown (with optional frontmatter) into
 * the page's HTML and metadata. Registered on the `onFile` hook so it runs for
 * every discovered markdown file.
 */
class MarkdownPlugin {
    constructor() {
        this.name = 'markdown';
    }
    onFile(page) {
        const raw = fs_1.default.readFileSync(page.sourcePath, 'utf8');
        const { frontmatter, html } = (0, markdown_1.parseMarkdown)(raw);
        page.html = html;
        page.frontmatter = frontmatter;
        page.title = frontmatter.title ?? (0, markdown_1.defaultTitle)(page.slug);
        page.date = frontmatter.date != null ? String(frontmatter.date) : undefined;
        page.tags = (0, markdown_1.normalizeTags)(frontmatter.tags);
        page.template = typeof frontmatter.template === 'string' ? frontmatter.template : undefined;
        page.layout = frontmatter.layout;
    }
}
exports.MarkdownPlugin = MarkdownPlugin;
//# sourceMappingURL=markdown-plugin.js.map