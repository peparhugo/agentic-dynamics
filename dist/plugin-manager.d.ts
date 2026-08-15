import { Plugin, PluginContext, FileContext } from './plugin.js';
import { PageMetadata } from './types.js';
export declare class PluginManager {
    private plugins;
    constructor(plugins: Plugin[]);
    onStart(context: PluginContext): Promise<void>;
    beforeBuild(context: PluginContext): Promise<void>;
    onFile(context: PluginContext, file: FileContext): Promise<void>;
    afterBuild(context: PluginContext, pages: PageMetadata[]): Promise<void>;
    onEnd(context: PluginContext): Promise<void>;
    getPlugins(): Plugin[];
    addPlugin(plugin: Plugin): void;
    removePlugin(pluginName: string): void;
    getPlugin(pluginName: string): Plugin | undefined;
}
//# sourceMappingURL=plugin-manager.d.ts.map