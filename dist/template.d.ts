export interface TemplateEngineOptions {
    templatesDir: string;
    layoutsDir: string;
    partialsDir: string;
}
export declare class TemplateEngine {
    private templatesDir;
    private layoutsDir;
    private partialsDir;
    private cache;
    constructor(options: TemplateEngineOptions);
    private registerPartials;
    private getTemplate;
    private getLayout;
    render(templateName: string, layoutName: string | undefined, data: any): string;
    renderWithLayout(content: string, layoutName: string | undefined, data: any): string;
}
export declare function createDefaultLayout(): string;
export declare function createDefaultIndexLayout(): string;
export declare function createDefaultNavPartial(): string;
//# sourceMappingURL=template.d.ts.map