"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.markdownToHtml = markdownToHtml;
const markdown_it_1 = __importDefault(require("markdown-it"));
const md = new markdown_it_1.default();
function markdownToHtml(markdown) {
    return md.render(markdown).trim();
}
//# sourceMappingURL=markdown.js.map