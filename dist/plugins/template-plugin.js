"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplatePlugin = void 0;
const render_1 = require("../render");
const templates_1 = require("../templates");
/**
 * Built-in plugin that renders each page through a Handlebars template.
 *
 * It prefers the layout named by the page's `template` metadata, falling back
 * to the `default` layout, and finally to the built-in HTML page renderer when
 * no layout matches. The final full-page HTML is stored in `page.rendered`.
 */
class TemplatePlugin {
    constructor(templatesDir) {
        this.name = 'template';
        this.engine = new templates_1.TemplateEngine(templatesDir);
    }
    onFile(page) {
        const rendered = this.engine.render(page.template, (0, render_1.pageToContext)(page));
        page.rendered = rendered ?? (0, render_1.renderPage)(page);
    }
}
exports.TemplatePlugin = TemplatePlugin;
