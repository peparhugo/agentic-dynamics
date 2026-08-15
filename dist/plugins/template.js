"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplatePlugin = void 0;
const templates_1 = require("../templates");
const render_1 = require("../render");
class TemplatePlugin {
    constructor(templatesDir) {
        this.name = 'template';
        this.engine = new templates_1.TemplateEngine(templatesDir);
    }
    async beforeBuild() {
        await this.engine.load();
    }
    renderPage(page) {
        return (0, render_1.renderPage)(page, this.engine);
    }
    renderIndex(pages) {
        return (0, render_1.renderIndex)(pages, this.engine);
    }
}
exports.TemplatePlugin = TemplatePlugin;
//# sourceMappingURL=template.js.map