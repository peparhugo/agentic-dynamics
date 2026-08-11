import { Page } from './types';
export interface TemplateEngineOptions {
    templatesDir: string;
}
export declare class TemplateEngine {
    private templatesDir;
    private layoutsDir;
    private partialsDir;
    private compiledTemplates;
    private compiledLayouts;
    constructor(options: TemplateEngineOptions);
    private loadPartials;
    private loadTemplate;
    private loadLayout;
    private getTemplate;
    private getLayout;
    hasTemplate(name: string): boolean;
    hasLayout(name: string): boolean;
    hasIndex(): boolean;
    render(page: Page, templateName?: string, layoutName?: string): string;
    renderIndex(pages: Page[]): string;
}
//# sourceMappingURL=template-engine.d.ts.map