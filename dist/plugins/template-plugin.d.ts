import { Plugin, PluginContext, FileContext } from '../plugin.js';
export declare class TemplatePlugin implements Plugin {
    name: string;
    version: string;
    private templateEngine;
    beforeBuild(context: PluginContext): Promise<void>;
    onFile(context: PluginContext, file: FileContext): Promise<void>;
    private renderPageWithTemplate;
    private generatePageHtml;
    private escapeHtml;
}
//# sourceMappingURL=template-plugin.d.ts.map