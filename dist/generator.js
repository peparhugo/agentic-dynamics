"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.readContentDirectory = exports.parseMarkdownFile = void 0;
exports.generateSite = generateSite;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const plugin_1 = require("./plugin");
const markdown_1 = require("./plugins/markdown");
const template_1 = require("./plugins/template");
const templates_1 = require("./templates");
var markdown_2 = require("./plugins/markdown");
Object.defineProperty(exports, "parseMarkdownFile", { enumerable: true, get: function () { return markdown_2.parseMarkdownFile; } });
Object.defineProperty(exports, "readContentDirectory", { enumerable: true, get: function () { return markdown_2.readContentDirectory; } });
function generateSite(contentDir, outputDir, templatesDir) {
    const plugins = [
        new markdown_1.MarkdownPlugin(),
        new template_1.TemplatePlugin(),
        ...(0, plugin_1.loadPluginsFromConfig)(),
    ];
    const options = { contentDir, outputDir, templatesDir };
    for (const p of plugins)
        if (p.onStart)
            p.onStart();
    for (const p of plugins)
        if (p.beforeBuild)
            p.beforeBuild(options);
    const pages = (0, markdown_1.readContentDirectory)(contentDir);
    if (pages.length === 0) {
        console.log(`No markdown files found in ${contentDir}`);
        for (const p of plugins)
            if (p.onEnd)
                p.onEnd();
        return 0;
    }
    fs_1.default.mkdirSync(outputDir, { recursive: true });
    const engine = templatesDir ? new templates_1.TemplateEngine(templatesDir) : null;
    const useTemplates = engine && engine.initialized;
    for (let i = 0; i < pages.length; i++) {
        let page = pages[i];
        for (const p of plugins) {
            if (p.onFile)
                page = p.onFile(page);
        }
        pages[i] = page;
        const html = useTemplates
            ? (engine.render(page) || (0, template_1.renderPage)(page))
            : (0, template_1.renderPage)(page);
        fs_1.default.writeFileSync(path_1.default.join(outputDir, `${page.slug}.html`), html);
    }
    const indexHtml = useTemplates
        ? (engine.renderIndex(pages) || (0, template_1.renderIndex)(pages))
        : (0, template_1.renderIndex)(pages);
    fs_1.default.writeFileSync(path_1.default.join(outputDir, 'index.html'), indexHtml);
    for (const p of plugins)
        if (p.afterBuild)
            p.afterBuild(options);
    for (const p of plugins)
        if (p.onEnd)
            p.onEnd();
    console.log(`Generated ${pages.length + 1} files in ${outputDir}`);
    return pages.length + 1;
}
//# sourceMappingURL=generator.js.map