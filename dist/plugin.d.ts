export interface PageData {
    slug: string;
    filename: string;
    content: string;
    metadata: Record<string, any>;
}
export interface BuildContext {
    contentDir: string;
    outputDir: string;
    templatesDir?: string;
    layoutsDir?: string;
    partialsDir?: string;
    pages: PageData[];
    cacheManager?: any;
    incremental?: boolean;
    pagesBuilt: number;
    pagesSkipped: number;
    [key: string]: any;
}
export interface Plugin {
    name: string;
    onStart?(context: BuildContext): Promise<void>;
    beforeBuild?(context: BuildContext): Promise<void>;
    onFile?(page: PageData, context: BuildContext): Promise<void>;
    afterBuild?(context: BuildContext): Promise<void>;
    onEnd?(context: BuildContext): Promise<void>;
}
export declare class PluginManager {
    private plugins;
    addPlugin(plugin: Plugin): void;
    callHook(hookName: keyof Plugin, context: BuildContext, page?: PageData): Promise<void>;
    getPlugins(): Plugin[];
}
//# sourceMappingURL=plugin.d.ts.map