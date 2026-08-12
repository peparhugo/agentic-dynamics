"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplatePlugin = void 0;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const template_1 = require("../template");
class TemplatePlugin {
    constructor() {
        this.name = 'template';
    }
    beforeBuild(ctx) {
        this.engine = new template_1.TemplateEngine(ctx.templatesDir);
    }
    onFile(page, ctx) {
        if (!this.engine)
            this.engine = new template_1.TemplateEngine(ctx.templatesDir);
        const html = (0, template_1.renderPage)(page, this.engine);
        const name = `${page.slug}.html`;
        fs_1.default.writeFileSync(path_1.default.join(ctx.outputDir, name), html, 'utf8');
        ctx.files.push(name);
    }
    afterBuild(ctx, _result) {
        if (!this.engine)
            this.engine = new template_1.TemplateEngine(ctx.templatesDir);
        const indexHtml = (0, template_1.renderIndex)(ctx.pages, this.engine);
        fs_1.default.writeFileSync(path_1.default.join(ctx.outputDir, 'index.html'), indexHtml, 'utf8');
        if (!ctx.files.includes('index.html'))
            ctx.files.push('index.html');
    }
}
exports.TemplatePlugin = TemplatePlugin;
