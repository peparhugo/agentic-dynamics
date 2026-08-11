"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SSGEngine = void 0;
class SSGEngine {
    constructor(options) {
        this.plugins = [];
        this.context = {
            pages: [],
            options,
        };
    }
    get pages() {
        return this.context.pages;
    }
    register(plugin) {
        this.plugins.push(plugin);
    }
    async build() {
        await this.runHook('onStart');
        await this.runHook('beforeBuild');
        for (let i = 0; i < this.context.pages.length; i++) {
            this.context.pages[i] = await this.runOnFile(this.context.pages[i]);
        }
        await this.runHook('afterBuild');
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