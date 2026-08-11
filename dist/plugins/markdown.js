"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MarkdownPlugin = void 0;
const marked_1 = require("marked");
exports.MarkdownPlugin = {
    name: 'markdown',
    onFile(page) {
        page.content = marked_1.marked.parse(page.content, { async: false });
    },
};
//# sourceMappingURL=markdown.js.map