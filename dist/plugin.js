"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PluginPipeline = void 0;
/**
 * Runs every plugin's hook for a given lifecycle stage, preserving plugin
 * order. Hooks may be synchronous or return a Promise.
 */
class PluginPipeline {
    constructor(plugins = []) {
        this.plugins = plugins;
    }
    async onStart() {
        for (const plugin of this.plugins) {
            await plugin.onStart?.();
        }
    }
    async beforeBuild() {
        for (const plugin of this.plugins) {
            await plugin.beforeBuild?.();
        }
    }
    async onFile(page) {
        for (const plugin of this.plugins) {
            await plugin.onFile?.(page);
        }
    }
    async afterBuild() {
        for (const plugin of this.plugins) {
            await plugin.afterBuild?.();
        }
    }
    async onEnd() {
        for (const plugin of this.plugins) {
            await plugin.onEnd?.();
        }
    }
}
exports.PluginPipeline = PluginPipeline;
