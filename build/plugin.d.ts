import { Page } from './types';
export interface SSGOptions {
    content: string;
    output: string;
    templates: string;
    port: number;
}
export interface PluginContext {
    pages: Page[];
    options: SSGOptions;
}
export interface Plugin {
    name: string;
    onStart?(context: PluginContext): Promise<void> | void;
    beforeBuild?(context: PluginContext): Promise<void> | void;
    afterBuild?(context: PluginContext): Promise<void> | void;
    onFile?(page: Page): Promise<Page> | Page;
    onEnd?(context: PluginContext): Promise<void> | void;
}
export interface PluginManager {
    plugins: Plugin[];
    register(plugin: Plugin): void;
    runHook(hook: keyof Plugin, context: PluginContext): Promise<void>;
    runOnFile(page: Page): Promise<Page>;
}
//# sourceMappingURL=plugin.d.ts.map