"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MarkdownPlugin = void 0;
const parser_1 = require("../parser");
class MarkdownPlugin {
    constructor() {
        this.name = 'markdown';
    }
    beforeBuild(context) {
        context.pages = (0, parser_1.parseDirectory)(context.options.content);
    }
}
exports.MarkdownPlugin = MarkdownPlugin;
//# sourceMappingURL=markdown.js.map