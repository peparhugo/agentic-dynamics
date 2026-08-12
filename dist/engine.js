"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.SiteEngine = void 0;
exports.sortPages = sortPages;
exports.createBuiltinPlugins = createBuiltinPlugins;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const plugin_1 = require("./plugin");
const cache_1 = require("./cache");
const markdown_1 = require("./plugins/markdown");
const template_1 = require("./plugins/template");
const devServer_1 = require("./plugins/devServer");
const template_2 = require("./template");
function sortPages(pages) {
    return [...pages].sort((a, b) => {
        const da = a.date ? new Date(a.date).getTime() : 0;
        const db = b.date ? new Date(b.date).getTime() : 0;
        if (da !== db)
            return db - da;
        return a.title.localeCompare(b.title);
    });
}
function createBuiltinPlugins() {
    return [new markdown_1.MarkdownPlugin(), new template_1.TemplatePlugin()];
}
class SiteEngine {
    constructor(options) {
        const cwd = options.cwd ?? process.cwd();
        const config = (0, plugin_1.loadConfig)(cwd, options.configFile);
        const plugins = [];
        const seen = new Set();
        const add = (plugin) => {
            if (seen.has(plugin.name))
                return;
            seen.add(plugin.name);
            plugins.push(plugin);
        };
        const builtins = createBuiltinPlugins();
        const markdown = builtins.find((p) => p.name === 'markdown');
        const template = builtins.find((p) => p.name === 'template');
        if (markdown)
            add(markdown);
        for (const plugin of (0, plugin_1.pluginsFromConfig)(config))
            add(plugin);
        for (const plugin of (0, plugin_1.discoverPlugins)(cwd))
            add(plugin);
        if (options.extraPlugins) {
            for (const plugin of options.extraPlugins)
                add(plugin);
        }
        if (template)
            add(template);
        if (options.devServer) {
            this.devServer = new devServer_1.DevServerPlugin();
            add(this.devServer);
        }
        this.plugins = plugins;
        this.context = {
            contentDir: options.contentDir,
            outputDir: options.outputDir,
            templatesDir: options.templatesDir ?? template_2.DEFAULT_TEMPLATES_DIR,
            config,
            pages: [],
            files: [],
        };
        this.incremental = options.incremental ?? false;
        this.clean = options.clean ?? false;
        this.stats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };
    }
    getPlugins() {
        return [...this.plugins];
    }
    getContext() {
        return this.context;
    }
    build() {
        const ctx = this.context;
        ctx.pages = [];
        ctx.files = [];
        (0, plugin_1.runHooks)(this.plugins, 'onStart', ctx);
        this.stats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };
        let cache;
        if (this.incremental) {
            const cacheFile = path_1.default.join(ctx.outputDir, cache_1.CACHE_FILE);
            if (this.clean && fs_1.default.existsSync(cacheFile)) {
                fs_1.default.rmSync(cacheFile);
            }
            cache = new cache_1.CacheManager(cacheFile, ctx.templatesDir, ctx.contentDir, ctx.outputDir);
            ctx.cache = cache;
        }
        else {
            ctx.cache = undefined;
        }
        fs_1.default.mkdirSync(ctx.outputDir, { recursive: true });
        (0, plugin_1.runHooks)(this.plugins, 'beforeBuild', ctx);
        const pages = sortPages(ctx.pages);
        ctx.pages = pages;
        for (const page of pages) {
            if (cache && cache.isUnchanged(page.filePath)) {
                const entry = cache.getEntry(page.filePath);
                this.stats.pagesSkipped++;
                if (entry)
                    this.stats.timeSavedMs += entry.renderMs;
                const name = `${page.slug}.html`;
                const outFile = path_1.default.join(ctx.outputDir, name);
                if (!fs_1.default.existsSync(outFile) && entry) {
                    fs_1.default.writeFileSync(outFile, entry.html, 'utf8');
                }
                if (!ctx.files.includes(name))
                    ctx.files.push(name);
                continue;
            }
            this.stats.pagesBuilt++;
            const started = Date.now();
            let current = page;
            for (const plugin of this.plugins) {
                if (typeof plugin.onFile === 'function') {
                    const out = plugin.onFile(current, ctx);
                    if (out)
                        current = out;
                }
            }
            if (cache) {
                const renderMs = Math.max(1, Date.now() - started);
                const name = `${current.slug}.html`;
                const outFile = path_1.default.join(ctx.outputDir, name);
                let html = '';
                try {
                    html = fs_1.default.readFileSync(outFile, 'utf8');
                }
                catch {
                    html = '';
                }
                cache.record(current.filePath, current, html, renderMs);
            }
        }
        const result = this.finishBuild();
        if (cache) {
            const activeFiles = ctx.pages.map((p) => p.filePath);
            cache.removeStale(activeFiles, ctx.outputDir);
            cache.save();
        }
        (0, plugin_1.runHooks)(this.plugins, 'onEnd', ctx);
        return result;
    }
    rebuild() {
        const ctx = this.context;
        ctx.pages = [];
        ctx.files = [];
        this.stats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };
        ctx.cache = undefined;
        this.runBuildPhase();
        return this.finishBuild();
    }
    runBuildPhase() {
        const ctx = this.context;
        fs_1.default.mkdirSync(ctx.outputDir, { recursive: true });
        (0, plugin_1.runHooks)(this.plugins, 'beforeBuild', ctx);
        const pages = sortPages(ctx.pages);
        ctx.pages = pages;
        for (const page of pages) {
            this.stats.pagesBuilt++;
            let current = page;
            for (const plugin of this.plugins) {
                if (typeof plugin.onFile === 'function') {
                    const out = plugin.onFile(current, ctx);
                    if (out)
                        current = out;
                }
            }
        }
    }
    finishBuild() {
        const ctx = this.context;
        const provisional = {
            pages: ctx.pages.length,
            outputDir: ctx.outputDir,
            files: [...ctx.files],
            pagesBuilt: this.stats.pagesBuilt,
            pagesSkipped: this.stats.pagesSkipped,
            timeSavedMs: this.stats.timeSavedMs,
        };
        (0, plugin_1.runHooks)(this.plugins, 'afterBuild', ctx, provisional);
        return {
            pages: ctx.pages.length,
            outputDir: ctx.outputDir,
            files: [...ctx.files],
            pagesBuilt: this.stats.pagesBuilt,
            pagesSkipped: this.stats.pagesSkipped,
            timeSavedMs: this.stats.timeSavedMs,
        };
    }
    serve(options) {
        const ctx = this.context;
        ctx.rebuild = () => {
            try {
                this.rebuild();
            }
            catch (err) {
                console.error('[ssg serve] rebuild failed:', err instanceof Error ? err.message : err);
            }
        };
        if (!this.devServer) {
            this.devServer = new devServer_1.DevServerPlugin();
            this.plugins.push(this.devServer);
        }
        if (typeof options.port === 'number') {
            this.devServer.setPort(options.port);
        }
        this.rebuild();
        (0, plugin_1.runHooks)(this.plugins, 'onStart', ctx);
        return this.devServer.getHandle();
    }
}
exports.SiteEngine = SiteEngine;
