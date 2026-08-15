"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MarkdownPlugin = void 0;
const cache_1 = require("../src/cache");
const markdown_1 = require("../src/markdown");
/**
 * Built-in plugin that parses raw Markdown content into structured pages.
 *
 * Runs during the `onFile` hook: it reads the raw source (frontmatter +
 * body) handed to it by the engine and replaces the placeholder page with
 * fully parsed page data, leaving template/layout rendering to later plugins.
 *
 * On incremental builds the raw source is hashed; when the hash matches the
 * cached manifest the previously parsed page (including its parsed
 * frontmatter and rendered markdown) is restored instead of re-parsing it.
 */
class MarkdownPlugin {
    constructor() {
        this.name = 'markdown';
    }
    async onFile(page, ctx) {
        const sourceHash = (0, cache_1.hashContent)(page.content);
        page.sourceHash = sourceHash;
        const entry = ctx.cache ? ctx.cache.get(page.slug) : undefined;
        if (entry && entry.sourceHash === sourceHash && entry.page) {
            (0, cache_1.applyParsedPage)(entry.page, page);
            return;
        }
        const parsed = (0, markdown_1.parseMarkdown)(page.content, page.sourcePath, page.slug);
        (0, cache_1.applyParsedPage)(parsed, page);
    }
}
exports.MarkdownPlugin = MarkdownPlugin;
