"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.build = build;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const parser_1 = require("./parser");
const generator_1 = require("./generator");
function build(options) {
    const { contentDir, outputDir } = options;
    const pages = (0, parser_1.parseMarkdownDirectory)(contentDir);
    fs_1.default.mkdirSync(outputDir, { recursive: true });
    for (const page of pages) {
        const html = (0, generator_1.generatePageHtml)(page);
        const outPath = path_1.default.join(outputDir, `${page.slug}.html`);
        fs_1.default.writeFileSync(outPath, html, 'utf-8');
    }
    const indexHtml = (0, generator_1.generateIndexHtml)(pages);
    const indexPath = path_1.default.join(outputDir, 'index.html');
    fs_1.default.writeFileSync(indexPath, indexHtml, 'utf-8');
}
