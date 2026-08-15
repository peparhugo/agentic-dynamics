"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MarkdownPlugin = void 0;
const markdown_1 = require("../src/markdown");
/**
 * Built-in plugin that parses raw Markdown content into structured pages.
 *
 * Runs during the `onFile` hook: it reads the raw source (frontmatter +
 * body) handed to it by the engine and replaces the placeholder page with
 * fully parsed page data, leaving template/layout rendering to later plugins.
 */
class MarkdownPlugin {
    constructor() {
        this.name = 'markdown';
    }
    async onFile(page, _ctx) {
        const parsed = (0, markdown_1.parseMarkdown)(page.content, page.sourcePath, page.slug);
        page.slug = parsed.slug;
        page.title = parsed.title;
        page.date = parsed.date;
        page.tags = parsed.tags;
        page.content = parsed.content;
        page.html = parsed.html;
        page.sourcePath = parsed.sourcePath;
        page.template = parsed.template;
        page.layout = parsed.layout;
        page.data = parsed.data;
    }
}
exports.MarkdownPlugin = MarkdownPlugin;
