import { Plugin, PluginContext, FileContext } from '../plugin.js';
export declare class MarkdownPlugin implements Plugin {
    name: string;
    version: string;
    onFile(context: PluginContext, file: FileContext): Promise<void>;
}
//# sourceMappingURL=markdown-plugin.d.ts.map