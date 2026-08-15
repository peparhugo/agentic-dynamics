import { PageMetadata, ParsedMarkdown } from './types.js';
export interface PluginContext {
    contentDir: string;
    outputDir: string;
    templatesDir?: string;
    options?: Record<string, unknown>;
}
export interface FileContext {
    filename: string;
    filePath: string;
    content: string;
    parsed?: ParsedMarkdown;
    html?: string;
    pageMetadata?: PageMetadata;
}
export interface Plugin {
    name: string;
    version?: string;
    onStart?(context: PluginContext): Promise<void>;
    beforeBuild?(context: PluginContext): Promise<void>;
    onFile?(context: PluginContext, file: FileContext): Promise<void>;
    afterBuild?(context: PluginContext, pages: PageMetadata[]): Promise<void>;
    onEnd?(context: PluginContext): Promise<void>;
}
export interface PluginConfig {
    plugins: (Plugin | string)[];
    [key: string]: unknown;
}
//# sourceMappingURL=plugin.d.ts.map