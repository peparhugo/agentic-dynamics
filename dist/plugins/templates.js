"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplatePlugin = void 0;
const perf_hooks_1 = require("perf_hooks");
const cache_1 = require("../src/cache");
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
 *
 * On incremental builds the page source hash (computed by the markdown plugin)
 * and a template fingerprint are compared against the cached manifest. When
 * both match, the cached rendered HTML is reused and the page counts as
 * skipped; otherwise the page is re-rendered and its output cached.
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
        const templateHash = (0, templates_1.computePageTemplateHash)(page, ctx.templateBundle);
        const entry = ctx.cache ? ctx.cache.get(page.slug) : undefined;
        const sourceHash = page.sourceHash ?? (0, cache_1.hashContent)(page.content);
        if (ctx.cache &&
            entry &&
            entry.html != null &&
            entry.sourceHash === sourceHash &&
            entry.templateHash === templateHash) {
            ctx.outputFiles.set(`${page.slug}.html`, entry.html);
            if (ctx.stats) {
                ctx.stats.skipped += 1;
                ctx.stats.timeSavedMs += entry.renderMs || 0;
            }
            return;
        }
        const start = perf_hooks_1.performance.now();
        const html = renderPageForBuild(page, ctx.templateBundle);
        const renderMs = perf_hooks_1.performance.now() - start;
        ctx.outputFiles.set(`${page.slug}.html`, html);
        if (ctx.cache) {
            ctx.cache.set(page.slug, {
                sourceHash,
                templateHash,
                page: (0, cache_1.snapshotPage)(page),
                html,
                renderMs,
            });
        }
        if (ctx.stats) {
            ctx.stats.built += 1;
        }
    }
    afterBuild(ctx) {
        if (!ctx.templateBundle) {
            throw new Error('templates not loaded');
        }
        ctx.outputFiles.set('index.html', renderIndexForBuild(ctx.pages, ctx.templateBundle));
        if (ctx.stats) {
            ctx.stats.built += 1;
        }
    }
}
exports.TemplatePlugin = TemplatePlugin;
