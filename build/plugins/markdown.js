"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MarkdownPlugin = void 0;
const parser_1 = require("../parser");
class MarkdownPlugin {
    constructor() {
        this.name = 'markdown';
    }
    beforeBuild(context) {
        const parseStats = { parsed: 0, skipped: 0 };
        context.pages = (0, parser_1.parseDirectory)(context.options.content, context.cache, parseStats);
    }
}
exports.MarkdownPlugin = MarkdownPlugin;
//# sourceMappingURL=markdown.js.map