"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SSGEngine = void 0;
const cache_1 = require("./cache");
class SSGEngine {
    constructor(options) {
        this.plugins = [];
        const cacheFile = options.cacheFile || '.ssg-cache.json';
        this.cache = new cache_1.BuildCache(cacheFile);
        this.context = {
            pages: [],
            options,
            cache: this.cache,
            stats: { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 },
        };
    }
    get pages() {
        return this.context.pages;
    }
    get stats() {
        return this.context.stats;
    }
    register(plugin) {
        this.plugins.push(plugin);
    }
    async build() {
        const startTime = Date.now();
        const options = this.context.options;
        if (options.clean) {
            this.cache.clear();
        }
        else if (options.incremental) {
            this.cache.load();
        }
        await this.runHook('onStart');
        await this.runHook('beforeBuild');
        for (let i = 0; i < this.context.pages.length; i++) {
            this.context.pages[i] = await this.runOnFile(this.context.pages[i]);
        }
        await this.runHook('afterBuild');
        if (options.incremental || options.clean) {
            this.cache.save();
        }
        const elapsed = Date.now() - startTime;
        if (this.context.stats && options.incremental) {
            this.context.stats.timeSavedMs = elapsed;
            console.log(`Site generated: ${this.context.stats.pagesBuilt} pages built, ` +
                `${this.context.stats.pagesSkipped} pages skipped`);
        }
    }
    async serve() {
        await this.runHook('onStart');
        await this.runBuildPipeline();
        const devPlugin = this.plugins.find((p) => p.name === 'devserver');
        if (!devPlugin) {
            throw new Error('DevServerPlugin is required for serving but was not registered');
        }
        const rebuildFn = async () => {
            await this.runBuildPipeline();
        };
        return devPlugin.startServer(this.context, rebuildFn);
    }
    async shutdown() {
        await this.runHook('onEnd');
    }
    async runBuildPipeline() {
        await this.runHook('beforeBuild');
        for (let i = 0; i < this.context.pages.length; i++) {
            this.context.pages[i] = await this.runOnFile(this.context.pages[i]);
        }
        await this.runHook('afterBuild');
        console.log(`Site rebuilt (${this.context.pages.length} pages)`);
    }
    async runHook(hook) {
        for (const plugin of this.plugins) {
            const fn = plugin[hook];
            if (fn) {
                await fn(this.context);
            }
        }
    }
    async runOnFile(page) {
        let result = page;
        for (const plugin of this.plugins) {
            if (plugin.onFile) {
                result = await plugin.onFile(result);
            }
        }
        return result;
    }
}
exports.SSGEngine = SSGEngine;
//# sourceMappingURL=engine.js.map