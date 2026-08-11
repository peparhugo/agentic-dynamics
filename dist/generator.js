"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.generateSite = generateSite;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const templates_1 = require("./templates");
function generateSite({ pages }, outputDir, templatesDir = './templates') {
    if (!fs_1.default.existsSync(outputDir)) {
        fs_1.default.mkdirSync(outputDir, { recursive: true });
    }
    const engine = new templates_1.TemplateEngine({ templatesDir });
    engine.init();
    for (const page of pages) {
        const html = engine.renderPage(page);
        fs_1.default.writeFileSync(path_1.default.join(outputDir, `${page.slug}.html`), html);
    }
    const indexHtml = engine.renderIndex(pages);
    fs_1.default.writeFileSync(path_1.default.join(outputDir, 'index.html'), indexHtml);
}
