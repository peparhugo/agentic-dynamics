import { Plugin, PageData, BuildContext } from '../plugin.js';
export declare class TemplatePlugin implements Plugin {
    name: string;
    private templateEngine;
    constructor();
    beforeBuild(context: BuildContext): Promise<void>;
    onFile(page: PageData, context: BuildContext): Promise<void>;
    afterBuild(context: BuildContext): Promise<void>;
    private generatePageHtml;
    private generateIndexHtml;
    private escapeHtml;
    private ensureDefaultTemplates;
}
//# sourceMappingURL=template-plugin.d.ts.map