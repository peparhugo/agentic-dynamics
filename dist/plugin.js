"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PluginPipeline = void 0;
/**
 * Runs each lifecycle hook across all plugins in registration order.
 */
class PluginPipeline {
    constructor(plugins) {
        this.plugins = plugins;
    }
    runSync(hook) {
        for (const plugin of this.plugins) {
            const fn = plugin[hook];
            if (fn) {
                void fn.call(plugin);
            }
        }
    }
    runFileSync(page) {
        for (const plugin of this.plugins) {
            if (plugin.onFile) {
                void plugin.onFile(page);
            }
        }
    }
    async run(hook) {
        for (const plugin of this.plugins) {
            const fn = plugin[hook];
            if (fn) {
                await fn.call(plugin);
            }
        }
    }
    async runFile(page) {
        for (const plugin of this.plugins) {
            if (plugin.onFile) {
                await plugin.onFile(page);
            }
        }
    }
}
exports.PluginPipeline = PluginPipeline;
//# sourceMappingURL=plugin.js.map