"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.processMarkdownFile = processMarkdownFile;
const frontmatter_1 = require("./frontmatter");
const markdown_1 = require("./markdown");
async function processMarkdownFile(filename, content) {
    const { data, content: markdownContent } = (0, frontmatter_1.parseFrontmatter)(content);
    const html = await (0, markdown_1.markdownToHtml)(markdownContent);
    const slug = filename.replace(/\.md$/, '');
    const title = data.title || slug.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    return {
        slug,
        title,
        date: data.date,
        tags: Array.isArray(data.tags) ? data.tags : undefined,
        html,
        ...data
    };
}
//# sourceMappingURL=page.js.map