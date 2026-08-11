import { PageTemplateData, IndexTemplateData } from './types';
export declare class TemplateEngine {
    private hbs;
    private templateDir;
    private templates;
    private layouts;
    private indexTemplate;
    constructor(templateDir?: string);
    private loadPartials;
    private loadLayouts;
    private loadTemplates;
    renderPage(data: PageTemplateData, templateName?: string, layoutName?: string): string;
    renderIndex(data: IndexTemplateData): string;
}
//# sourceMappingURL=template-engine.d.ts.map