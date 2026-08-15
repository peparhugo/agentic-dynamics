export class PluginManager {
    constructor(plugins) {
        this.plugins = [];
        this.plugins = plugins;
    }
    async onStart(context) {
        for (const plugin of this.plugins) {
            if (plugin.onStart) {
                await plugin.onStart(context);
            }
        }
    }
    async beforeBuild(context) {
        for (const plugin of this.plugins) {
            if (plugin.beforeBuild) {
                await plugin.beforeBuild(context);
            }
        }
    }
    async onFile(context, file) {
        for (const plugin of this.plugins) {
            if (plugin.onFile) {
                await plugin.onFile(context, file);
            }
        }
    }
    async afterBuild(context, pages) {
        for (const plugin of this.plugins) {
            if (plugin.afterBuild) {
                await plugin.afterBuild(context, pages);
            }
        }
    }
    async onEnd(context) {
        for (const plugin of this.plugins) {
            if (plugin.onEnd) {
                await plugin.onEnd(context);
            }
        }
    }
    getPlugins() {
        return this.plugins;
    }
    addPlugin(plugin) {
        this.plugins.push(plugin);
    }
    removePlugin(pluginName) {
        this.plugins = this.plugins.filter((p) => p.name !== pluginName);
    }
    getPlugin(pluginName) {
        return this.plugins.find((p) => p.name === pluginName);
    }
}
//# sourceMappingURL=plugin-manager.js.map