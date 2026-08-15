"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MarkdownPlugin = void 0;
const markdown_1 = require("../markdown");
/**
 * Built-in plugin that parses Markdown documents.
 *
 * The engine creates each `Page` with the raw file source in `content`. This
 * plugin parses the frontmatter, rewrites `content` to the stripped Markdown
 * body and fills `html` with the rendered body HTML.
 */
class MarkdownPlugin {
    constructor() {
        this.name = 'markdown';
    }
    onFile(page) {
        const { meta, content, html } = (0, markdown_1.parseMarkdown)(page.content);
        page.title = meta.title || page.slug;
        page.date = meta.date;
        page.tags = meta.tags;
        page.template = meta.template;
        page.content = content;
        page.html = html;
    }
}
exports.MarkdownPlugin = MarkdownPlugin;
