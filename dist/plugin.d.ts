import { PageData } from './page';
export interface PluginContext {
    contentDir: string;
    outputDir: string;
    templateDir?: string;
}
export interface Plugin {
    name: string;
    onStart?: (context: PluginContext) => Promise<void>;
    beforeBuild?: (context: PluginContext) => Promise<void>;
    onFile?: (page: PageData, context: PluginContext) => Promise<PageData>;
    afterBuild?: (pages: PageData[], context: PluginContext) => Promise<void>;
    onEnd?: (context: PluginContext) => Promise<void>;
}
export declare class PluginManager {
    private plugins;
    register(plugin: Plugin): void;
    runOnStart(context: PluginContext): Promise<void>;
    runBeforeBuild(context: PluginContext): Promise<void>;
    runOnFile(page: PageData, context: PluginContext): Promise<PageData>;
    runAfterBuild(pages: PageData[], context: PluginContext): Promise<void>;
    runOnEnd(context: PluginContext): Promise<void>;
}
//# sourceMappingURL=plugin.d.ts.map