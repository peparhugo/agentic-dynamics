"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PluginPipeline = void 0;
/**
 * Runs a lifecycle hook across all plugins in order, awaiting each hook to
 * completion before moving on to the next plugin.
 */
class PluginPipeline {
    constructor(plugins) {
        this.plugins = plugins;
    }
    getPlugins() {
        return this.plugins;
    }
    async run(hook, ...args) {
        for (const plugin of this.plugins) {
            const fn = plugin[hook];
            if (typeof fn === 'function') {
                await fn.apply(plugin, args);
            }
        }
    }
}
exports.PluginPipeline = PluginPipeline;
