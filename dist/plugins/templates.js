"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplatePlugin = void 0;
const templates_1 = require("../src/templates");
const render_1 = require("../src/render");
function renderPageForBuild(page, bundle) {
    if (!bundle.exists) {
        if (page.template) {
            throw new Error(`template not found: "${page.template}" (no templates directory configured)`);
        }
        return (0, render_1.renderPageHtml)(page);
    }
    return (0, templates_1.renderPageTemplate)(page, bundle);
}
function renderIndexForBuild(pages, bundle) {
    return (0, templates_1.renderIndexTemplate)(pages, bundle) ?? (0, render_1.renderIndexHtml)(pages);
}
/**
 * Built-in plugin that renders pages and the site index through Handlebars
 * templates.
 *
 * Templates are loaded during `beforeBuild`; each page is rendered in the
 * `onFile` hook and the index is rendered in `afterBuild`. Rendered output is
 * contributed to the engine's output files so the engine can write it to disk.
 */
class TemplatePlugin {
    constructor() {
        this.name = 'templates';
    }
    async beforeBuild(ctx) {
        ctx.templateBundle = await (0, templates_1.loadTemplates)(ctx.options.templatesDir ?? 'templates');
    }
    onFile(page, ctx) {
        if (!ctx.templateBundle) {
            throw new Error('templates not loaded');
        }
        ctx.outputFiles.set(`${page.slug}.html`, renderPageForBuild(page, ctx.templateBundle));
    }
    afterBuild(ctx) {
        if (!ctx.templateBundle) {
            throw new Error('templates not loaded');
        }
        ctx.outputFiles.set('index.html', renderIndexForBuild(ctx.pages, ctx.templateBundle));
    }
}
exports.TemplatePlugin = TemplatePlugin;
