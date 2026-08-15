export class PluginManager {
    constructor() {
        this.plugins = [];
    }
    addPlugin(plugin) {
        this.plugins.push(plugin);
    }
    async callHook(hookName, context, page) {
        for (const plugin of this.plugins) {
            const hook = plugin[hookName];
            if (typeof hook === 'function') {
                if (hookName === 'onFile' && page) {
                    await hook(page, context);
                }
                else {
                    await hook(context);
                }
            }
        }
    }
    getPlugins() {
        return this.plugins;
    }
}
//# sourceMappingURL=plugin.js.map