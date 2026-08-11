"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.SSGEngine = void 0;
exports.build = build;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const markdown_plugin_1 = require("./plugins/markdown-plugin");
const template_plugin_1 = require("./plugins/template-plugin");
const cache_1 = require("./cache");
class SSGEngine {
    constructor(options) {
        this.plugins = [];
        this.options = options;
        this.loadPlugins();
    }
    loadPlugins() {
        this.plugins.push(new markdown_plugin_1.MarkdownPlugin());
        this.plugins.push(new template_plugin_1.TemplatePlugin());
        this.loadConfigPlugins();
    }
    loadConfigPlugins() {
        const configDirs = [process.cwd(), __dirname, path_1.default.resolve('.')];
        const configNames = ['ssg.config.js', 'ssg.config.ts'];
        for (const dir of configDirs) {
            for (const name of configNames) {
                const configPath = path_1.default.join(dir, name);
                if (fs_1.default.existsSync(configPath)) {
                    try {
                        const cfg = require(configPath);
                        const config = cfg.default || cfg;
                        if (config.plugins) {
                            for (const entry of config.plugins) {
                                if (typeof entry === 'string') {
                                    const plugin = this.tryLoadPlugin(entry);
                                    if (plugin && !this.plugins.some(p => p.name === plugin.name)) {
                                        this.plugins.push(plugin);
                                    }
                                }
                            }
                        }
                    }
                    catch {
                        // Config loading is best-effort
                    }
                    return;
                }
            }
        }
    }
    tryLoadPlugin(name) {
        const builtinMap = {
            'markdown': new markdown_plugin_1.MarkdownPlugin(),
            'template': new template_plugin_1.TemplatePlugin(),
        };
        if (builtinMap[name]) {
            return builtinMap[name];
        }
        try {
            const mod = require(path_1.default.resolve(name));
            const PluginClass = mod.default || mod[name + 'Plugin'] || mod;
            if (typeof PluginClass === 'function') {
                const instance = new PluginClass();
                if (this.isPlugin(instance)) {
                    return instance;
                }
            }
            return null;
        }
        catch {
            return null;
        }
    }
    isPlugin(obj) {
        return obj && typeof obj.name === 'string' && (typeof obj.onStart === 'function' ||
            typeof obj.beforeBuild === 'function' ||
            typeof obj.onFile === 'function' ||
            typeof obj.afterBuild === 'function' ||
            typeof obj.onEnd === 'function');
    }
    build() {
        const { outputDir, incremental, clean } = this.options;
        if (!fs_1.default.existsSync(outputDir)) {
            fs_1.default.mkdirSync(outputDir, { recursive: true });
        }
        const context = {
            options: this.options,
            pages: [],
            outputDir,
        };
        let cache = null;
        if (incremental) {
            cache = new cache_1.CacheManager(path_1.default.join(outputDir, '.ssg-cache.json'));
            if (clean) {
                cache.delete();
            }
            cache.load();
            const templatesHash = cache.computeTemplatesHash(this.options.templateDir || '');
            const manifest = cache.getManifest();
            const templatesChanged = !manifest || manifest.templatesHash !== templatesHash;
            context.cache = cache;
            context.templatesChanged = templatesChanged;
            context.incremental = true;
        }
        for (const plugin of this.plugins) {
            if (plugin.onStart) {
                plugin.onStart(context);
            }
        }
        for (const plugin of this.plugins) {
            if (plugin.beforeBuild) {
                plugin.beforeBuild(context);
            }
        }
        for (const page of context.pages) {
            const isCached = incremental && !!page._fromCache;
            if (isCached) {
                if (cache) {
                    cache.incrementSkipped();
                }
            }
            for (const plugin of this.plugins) {
                if (plugin.onFile) {
                    plugin.onFile(page, context);
                }
            }
        }
        for (const plugin of this.plugins) {
            if (plugin.afterBuild) {
                plugin.afterBuild(context);
            }
        }
        if (incremental && cache) {
            const templatesHash = cache.currentTemplatesHash;
            const newManifest = cache.buildManifest(templatesHash);
            if (Object.keys(newManifest.pages).length > 0) {
                cache.save(newManifest);
            }
        }
        for (const plugin of this.plugins) {
            if (plugin.onEnd) {
                plugin.onEnd(context);
            }
        }
        const stats = cache
            ? cache.getStats()
            : { pagesBuilt: context.pages.length, pagesSkipped: 0 };
        if (incremental) {
            console.log(`Build complete: ${stats.pagesBuilt} page(s) built, ${stats.pagesSkipped} page(s) skipped`);
        }
        return { stats };
    }
}
exports.SSGEngine = SSGEngine;
function build(options) {
    const engine = new SSGEngine(options);
    return engine.build();
}
//# sourceMappingURL=ssg.js.map