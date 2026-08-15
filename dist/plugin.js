"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PluginManager = void 0;
class PluginManager {
    constructor() {
        this.plugins = [];
    }
    register(plugin) {
        this.plugins.push(plugin);
    }
    async runOnStart(context) {
        for (const plugin of this.plugins) {
            if (plugin.onStart) {
                await plugin.onStart(context);
            }
        }
    }
    async runBeforeBuild(context) {
        for (const plugin of this.plugins) {
            if (plugin.beforeBuild) {
                await plugin.beforeBuild(context);
            }
        }
    }
    async runOnFile(page, context) {
        let result = page;
        for (const plugin of this.plugins) {
            if (plugin.onFile) {
                result = await plugin.onFile(result, context);
            }
        }
        return result;
    }
    async runAfterBuild(pages, context) {
        for (const plugin of this.plugins) {
            if (plugin.afterBuild) {
                await plugin.afterBuild(pages, context);
            }
        }
    }
    async runOnEnd(context) {
        for (const plugin of this.plugins) {
            if (plugin.onEnd) {
                await plugin.onEnd(context);
            }
        }
    }
}
exports.PluginManager = PluginManager;
//# sourceMappingURL=plugin.js.map