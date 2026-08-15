"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.markdownToHtml = markdownToHtml;
const marked_1 = require("marked");
async function markdownToHtml(markdown) {
    return await (0, marked_1.marked)(markdown);
}
//# sourceMappingURL=markdown.js.map