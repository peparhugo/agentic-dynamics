"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.generateSite = generateSite;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const templates_1 = require("./templates");
function generateSite(pages, outputDir, templatesDir) {
    const resolved = path_1.default.resolve(outputDir);
    fs_1.default.mkdirSync(resolved, { recursive: true });
    const engine = new templates_1.TemplateEngine(templatesDir || './templates');
    for (const page of pages) {
        const body = engine.renderPage(page);
        const html = engine.renderLayout(page.frontmatter.title, body, page.frontmatter.layout);
        fs_1.default.writeFileSync(path_1.default.join(resolved, `${page.slug}.html`), html, 'utf-8');
    }
    const indexBody = engine.renderIndex(pages);
    const indexHtml = engine.renderLayout('Site Index', indexBody);
    fs_1.default.writeFileSync(path_1.default.join(resolved, 'index.html'), indexHtml, 'utf-8');
}
//# sourceMappingURL=generator.js.map