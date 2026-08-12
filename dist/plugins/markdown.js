"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.MarkdownPlugin = void 0;
const fs_1 = __importDefault(require("fs"));
const markdown_1 = require("../markdown");
class MarkdownPlugin {
    constructor() {
        this.name = 'markdown';
    }
    beforeBuild(ctx) {
        if (!fs_1.default.existsSync(ctx.contentDir)) {
            throw new Error(`content directory not found: ${ctx.contentDir}`);
        }
        ctx.pages = (0, markdown_1.readPages)(ctx.contentDir);
    }
}
exports.MarkdownPlugin = MarkdownPlugin;
