"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MarkdownPlugin = void 0;
const markdown_1 = require("../markdown");
class MarkdownPlugin {
    constructor() {
        this.name = 'markdown';
    }
    onFile(page) {
        page.contentHtml = (0, markdown_1.markdownToHtml)(page.content ?? '');
        return page;
    }
}
exports.MarkdownPlugin = MarkdownPlugin;
//# sourceMappingURL=markdown.js.map